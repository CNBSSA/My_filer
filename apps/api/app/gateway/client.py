"""NRS gateway client (P6.3).

Wraps the signed POST to NRS. Synchronous today; the retry schedule here
mirrors the Celery backoff that will be added in P6.4/P6.5 when Redis is
available — same `(2, 4, 8, 16)` seconds per KNOWLEDGE_BASE §9.

Design notes:

- The adapter stays small. Canonicalization + signing are in `signing.py`;
  payload construction is the caller's job. The client's contract is:
  "sign, send, parse, retry transport errors".
- `HttpClient` is a Protocol so tests inject a fake without monkey-patching
  httpx.
- When credentials are missing we refuse to call the network. Callers
  should route through `simulate_submission` in that case — see the
  service layer for the gating.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import httpx

from app.gateway.jwt_signing import sign_jwt
from app.gateway.signing import sign_request
from app.gateway.timestamps import iso_20022_now

log = logging.getLogger("mai_filer.gateway")


DEFAULT_BACKOFF_SECONDS = (2, 4, 8, 16)


@dataclass
class NRSResponse:
    """Success envelope returned by the NRS after accepting a pack."""

    irn: str  # Invoice Reference Number
    csid: str  # Cryptographic Stamp Identifier
    qr_payload: str  # String encoded into the displayed QR
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class NRSRejection:
    """Vendor-rejected submission (4xx). Not retried."""

    code: str
    message: str
    raw: dict[str, Any] = field(default_factory=dict)


class NRSTransportError(RuntimeError):
    """Escalated for 5xx / network failures after retries are exhausted."""


class NRSAuthError(RuntimeError):
    """Raised when required NRS credentials are missing. Caller should
    route to simulation mode instead of hitting the network."""


class HttpClient(Protocol):
    def post(
        self,
        url: str,
        *,
        content: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> "HttpResponse":
        ...


class HttpResponse(Protocol):
    status_code: int

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


@dataclass
class NRSCredentials:
    client_id: str
    client_secret: str
    business_id: str

    def assert_present(self) -> None:
        missing = [
            name
            for name, value in (
                ("NRS_CLIENT_ID", self.client_id),
                ("NRS_CLIENT_SECRET", self.client_secret),
                ("NRS_BUSINESS_ID", self.business_id),
            )
            if not value
        ]
        if missing:
            raise NRSAuthError(
                "NRS credentials missing: " + ", ".join(missing)
            )


class NRSClient:
    """Signed POST to the NRS filing endpoint with sync retry."""

    def __init__(
        self,
        *,
        base_url: str,
        credentials: NRSCredentials,
        http: HttpClient | None = None,
        timeout: float = 20.0,
        backoff_seconds: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        now_factory: Callable[[], str] = iso_20022_now,
        auth_scheme: str = "hmac",
        jwt_algorithm: str = "HS256",
        jwt_private_key: str = "",
        jwt_issuer: str = "mai-filer",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._credentials = credentials
        self._http: HttpClient = http or httpx.Client()  # type: ignore[assignment]
        self._timeout = timeout
        self._backoff = backoff_seconds
        self._sleep = sleep
        self._now_factory = now_factory
        self._auth_scheme = auth_scheme.lower()
        self._jwt_algorithm = jwt_algorithm
        self._jwt_private_key = jwt_private_key
        self._jwt_issuer = jwt_issuer

    def _auth_headers(
        self, *, payload: str, timestamp: str, audience: str
    ) -> dict[str, str]:
        """Build the outbound request headers for the configured auth scheme."""
        base = {
            "Content-Type": "application/json",
            "X-API-Key": self._credentials.client_id,
            "X-API-Business-Id": self._credentials.business_id,
            "X-API-Timestamp": timestamp,
        }
        if self._auth_scheme == "jwt":
            key = self._jwt_private_key or self._credentials.client_secret
            token = sign_jwt(
                payload=payload,
                business_id=self._credentials.business_id,
                issuer=self._jwt_issuer,
                audience=audience,
                secret_or_private_key=key,
                algorithm=self._jwt_algorithm,
            )
            base["Authorization"] = f"Bearer {token}"
            return base
        # Default: HMAC-SHA256 per KNOWLEDGE_BASE §9.
        base["X-API-Signature"] = sign_request(
            payload=payload,
            timestamp=timestamp,
            secret=self._credentials.client_secret,
        )
        return base

    def submit_filing(
        self, pack: dict[str, Any], *, path: str = "/efiling/pit/submit"
    ) -> NRSResponse | NRSRejection:
        """Submit a filing pack; return a typed response or rejection.

        Raises:
            NRSAuthError      — credentials missing; caller should simulate.
            NRSTransportError — 5xx or network after retries exhausted.
        """
        self._credentials.assert_present()

        payload = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
        url = f"{self._base_url}{path}"

        last_status: int | None = None
        last_body: str | None = None

        for attempt in range(len(self._backoff) + 1):
            timestamp = self._now_factory()
            headers = self._auth_headers(payload=payload, timestamp=timestamp, audience=self._base_url)

            try:
                response = self._http.post(
                    url,
                    content=payload.encode("utf-8"),
                    headers=headers,
                    timeout=self._timeout,
                )
            except Exception as exc:
                log.warning("NRS transport failure attempt %d: %s", attempt + 1, exc)
                if attempt >= len(self._backoff):
                    raise NRSTransportError(f"NRS transport failure: {exc}") from exc
                self._sleep(self._backoff[attempt])
                continue

            last_status = response.status_code
            last_body = getattr(response, "text", "")

            if 200 <= response.status_code < 300:
                return _parse_success(response.json() or {})

            if 400 <= response.status_code < 500:
                return _parse_rejection(response)

            # 5xx / unknown → retry.
            log.warning(
                "NRS %s on attempt %d; body=%s",
                response.status_code,
                attempt + 1,
                last_body[:200] if last_body else "",
            )
            if attempt >= len(self._backoff):
                raise NRSTransportError(
                    f"NRS returned {response.status_code} after retries: {last_body}"
                )
            self._sleep(self._backoff[attempt])

        raise NRSTransportError(
            f"NRS submission exhausted retries (last status={last_status})"
        )


def _parse_success(body: dict[str, Any]) -> NRSResponse:
    return NRSResponse(
        irn=str(body.get("irn") or body.get("IRN") or ""),
        csid=str(body.get("csid") or body.get("CSID") or ""),
        qr_payload=str(body.get("qr") or body.get("qr_payload") or ""),
        raw=body,
    )


def _parse_rejection(response: HttpResponse) -> NRSRejection:
    try:
        body = response.json() or {}
    except Exception:
        body = {}
    return NRSRejection(
        code=str(body.get("code") or f"HTTP-{response.status_code}"),
        message=str(body.get("message") or getattr(response, "text", "")),
        raw=body,
    )


def build_default_nrs_client() -> NRSClient:
    """Factory reading credentials from settings. Raises `NRSAuthError`
    only on actual submission, not at construction.

    Secrets are resolved via the `secret()` helper so an AWS Secrets
    Manager backend picks up prod values without code changes.
    """
    from app.config import get_settings
    from app.secret_store import secret

    s = get_settings()
    return NRSClient(
        base_url=s.nrs_base_url,
        credentials=NRSCredentials(
            client_id=secret("nrs_client_id") or s.nrs_client_id,
            client_secret=secret("nrs_client_secret") or s.nrs_client_secret,
            business_id=secret("nrs_business_id") or s.nrs_business_id,
        ),
        auth_scheme=s.nrs_auth_scheme,
        jwt_algorithm=s.nrs_jwt_algorithm,
        jwt_private_key=secret("nrs_jwt_private_key") or s.nrs_jwt_private_key,
        jwt_issuer=s.jwt_issuer,
    )
