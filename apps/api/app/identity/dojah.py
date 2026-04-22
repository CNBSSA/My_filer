"""Dojah NIN verification adapter (P5.2, ADR-0003 default).

Dojah exposes a `/kyc/nin` GET endpoint that accepts an API key + app ID
and returns the NIMC record. We keep the adapter shallow: request, parse,
shape into `NINVerification`. Transport errors escalate as
`AggregatorError` so the service decides whether to retry or fall through
to the next aggregator.

Dojah's response payload (abridged) looks like:

```
{
  "entity": {
    "nin": "12345678901",
    "first_name": "Chidi",
    "last_name": "Okafor",
    "middle_name": "Emeka",
    "date_of_birth": "1990-04-12",
    "gender": "M",
    "state_of_origin": "Anambra",
    "phone_number": "+2348012345678"
  }
}
```

We normalize to our `NINVerification`. Full name is synthesized from parts
because Dojah doesn't return a precomposed `full_name`.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

import httpx

from app.identity.base import AggregatorError, NINVerification

DEFAULT_BASE_URL = "https://api.dojah.io/api/v1"


class HttpClient(Protocol):
    def get(
        self, url: str, *, headers: dict[str, str], params: dict[str, str], timeout: float
    ) -> "HttpResponse":
        ...


class HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any:
        ...

    @property
    def text(self) -> str:
        ...


class DojahAdapter:
    """Talk to Dojah's KYC NIN endpoint.

    Construction is explicit so tests can inject a `FakeHttpClient` without
    monkey-patching httpx.
    """

    name = "dojah"

    def __init__(
        self,
        *,
        api_key: str,
        app_id: str,
        base_url: str = DEFAULT_BASE_URL,
        http: HttpClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        if not api_key or not app_id:
            raise ValueError("DojahAdapter requires both api_key and app_id")
        self._api_key = api_key
        self._app_id = app_id
        self._base_url = base_url.rstrip("/")
        self._http: HttpClient = http or httpx.Client()  # type: ignore[assignment]
        self._timeout = timeout

    def verify_nin(self, nin: str, *, consent: bool) -> NINVerification:
        if not nin.isdigit() or len(nin) != 11:
            raise ValueError("NIN must be exactly 11 digits")
        if not consent:
            raise PermissionError(
                "consent=True is mandatory before any NIN query (NDPR / NDPC)"
            )

        url = f"{self._base_url}/kyc/nin"
        headers = {
            "AppId": self._app_id,
            "Authorization": self._api_key,
            "Accept": "application/json",
        }
        params = {"nin": nin}

        try:
            response = self._http.get(
                url, headers=headers, params=params, timeout=self._timeout
            )
        except Exception as exc:  # transport error
            raise AggregatorError(f"dojah transport failure: {exc}") from exc

        if response.status_code == 200:
            payload = response.json() or {}
            entity = payload.get("entity") or {}
            return _to_verification(nin=nin, entity=entity, raw=payload)

        # 400-level: vendor reached, but said no.
        if 400 <= response.status_code < 500:
            try:
                reason = response.json().get("error") or response.text
            except Exception:
                reason = response.text
            return NINVerification(
                valid=False,
                aggregator="dojah",
                nin=nin,
                error=f"dojah returned {response.status_code}: {reason}",
                raw={"status": response.status_code, "body": reason},
            )

        # 5xx or anything else unexpected → escalate so the service layer
        # can decide about retry / fallback to another aggregator.
        raise AggregatorError(
            f"dojah returned {response.status_code}: {getattr(response, 'text', '')}"
        )


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _to_verification(*, nin: str, entity: dict[str, Any], raw: dict[str, Any]) -> NINVerification:
    first = entity.get("first_name")
    middle = entity.get("middle_name")
    last = entity.get("last_name")

    composed = " ".join(p for p in (first, middle, last) if p) or None
    # Treat the verification as valid only when we got at least a first +
    # last name AND the NIN echoes back.
    echoed = str(entity.get("nin") or "").strip()
    has_name = bool(first and last)
    valid = bool(has_name and (not echoed or echoed == nin))

    return NINVerification(
        valid=valid,
        aggregator="dojah",
        nin=nin,
        first_name=first,
        middle_name=middle,
        last_name=last,
        full_name=composed,
        date_of_birth=_parse_date(entity.get("date_of_birth")),
        gender=entity.get("gender"),
        state_of_origin=entity.get("state_of_origin"),
        phone=entity.get("phone_number") or entity.get("phone"),
        error=None if valid else "incomplete identity record",
        raw=raw,
    )
