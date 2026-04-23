"""NRS client tests (P6.3, P6.7) — mocked HttpClient, no network."""

from __future__ import annotations

import json

import pytest

from app.gateway.client import (
    NRSAuthError,
    NRSClient,
    NRSCredentials,
    NRSRejection,
    NRSResponse,
    NRSTransportError,
)
from app.gateway.signing import verify_signature


class FakeResponse:
    def __init__(self, *, status_code: int, body: dict | str | None = None) -> None:
        self.status_code = status_code
        self._body = body or {}
        self.text = body if isinstance(body, str) else json.dumps(body or {})

    def json(self):
        return self._body if isinstance(self._body, dict) else {}


class FakeHttp:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def post(self, url, *, content, headers, timeout):
        self.calls.append(
            {"url": url, "content": content, "headers": headers, "timeout": timeout}
        )
        if not self._responses:
            raise AssertionError("script exhausted")
        head = self._responses.pop(0)
        if isinstance(head, Exception):
            raise head
        return head


CREDS = NRSCredentials(
    client_id="client-abc",
    client_secret="secret-xyz",
    business_id="biz-42",
)


def _client(http: FakeHttp, *, now_factory=None) -> NRSClient:
    return NRSClient(
        base_url="https://api.nrs.gov.ng/v1",
        credentials=CREDS,
        http=http,
        sleep=lambda _s: None,
        now_factory=now_factory or (lambda: "2026-04-22T10:00:00.000Z"),
    )


# ---------------------------------------------------------------------------
# Credential gating
# ---------------------------------------------------------------------------


def test_missing_credentials_raises_auth_error() -> None:
    client = NRSClient(
        base_url="x",
        credentials=NRSCredentials(client_id="", client_secret="", business_id=""),
        http=FakeHttp([]),
        sleep=lambda _s: None,
    )
    with pytest.raises(NRSAuthError):
        client.submit_filing({"any": "pack"})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_accepted_response_is_parsed() -> None:
    http = FakeHttp(
        [
            FakeResponse(
                status_code=200,
                body={
                    "irn": "NRS-IRN-XYZ-001",
                    "csid": "CSID-SAMPLE-123",
                    "qr_payload": "nrs://verify/NRS-IRN-XYZ-001",
                },
            )
        ]
    )
    client = _client(http)
    result = client.submit_filing({"tax_year": 2026})
    assert isinstance(result, NRSResponse)
    assert result.irn == "NRS-IRN-XYZ-001"
    assert result.csid == "CSID-SAMPLE-123"
    assert result.qr_payload == "nrs://verify/NRS-IRN-XYZ-001"


def test_request_is_hmac_signed() -> None:
    http = FakeHttp([FakeResponse(status_code=200, body={"irn": "x"})])
    client = _client(http)
    client.submit_filing({"tax_year": 2026})

    call = http.calls[0]
    headers = call["headers"]
    # Required headers are present.
    assert headers["X-API-Key"] == CREDS.client_id
    assert headers["X-API-Business-Id"] == CREDS.business_id
    assert headers["X-API-Timestamp"] == "2026-04-22T10:00:00.000Z"
    assert headers["Content-Type"] == "application/json"
    # Signature verifies against payload + timestamp + secret.
    payload = call["content"].decode("utf-8")
    assert verify_signature(
        payload=payload,
        timestamp=headers["X-API-Timestamp"],
        secret=CREDS.client_secret,
        signature=headers["X-API-Signature"],
    ) is True


# ---------------------------------------------------------------------------
# Rejections (4xx)
# ---------------------------------------------------------------------------


def test_4xx_returns_rejection_no_retry() -> None:
    http = FakeHttp(
        [
            FakeResponse(
                status_code=422,
                body={"code": "NRS-PAYLOAD-001", "message": "NIN missing"},
            )
        ]
    )
    client = _client(http)
    result = client.submit_filing({})
    assert isinstance(result, NRSRejection)
    assert result.code == "NRS-PAYLOAD-001"
    assert "NIN missing" in result.message
    assert len(http.calls) == 1  # no retry on 4xx


# ---------------------------------------------------------------------------
# 5xx + transport retries
# ---------------------------------------------------------------------------


def test_5xx_retries_then_succeeds() -> None:
    http = FakeHttp(
        [
            FakeResponse(status_code=503, body="maintenance"),
            FakeResponse(status_code=502, body="bad gateway"),
            FakeResponse(status_code=200, body={"irn": "RECOVERED"}),
        ]
    )
    client = _client(http)
    result = client.submit_filing({})
    assert isinstance(result, NRSResponse)
    assert result.irn == "RECOVERED"
    assert len(http.calls) == 3


def test_5xx_exhausts_retries_raises_transport_error() -> None:
    http = FakeHttp([FakeResponse(status_code=503, body="oops")] * 10)
    client = _client(http)
    with pytest.raises(NRSTransportError):
        client.submit_filing({})
    # 1 initial + 4 retries = 5 attempts.
    assert len(http.calls) == 5


def test_transport_exception_retries_then_raises() -> None:
    http = FakeHttp([ConnectionError("boom")] * 10)
    client = _client(http)
    with pytest.raises(NRSTransportError):
        client.submit_filing({})
    assert len(http.calls) == 5


def test_transport_exception_recovers_mid_retry() -> None:
    http = FakeHttp(
        [
            ConnectionError("boom"),
            FakeResponse(status_code=200, body={"irn": "BOUNCED-BACK"}),
        ]
    )
    client = _client(http)
    result = client.submit_filing({})
    assert isinstance(result, NRSResponse)
    assert result.irn == "BOUNCED-BACK"


# ---------------------------------------------------------------------------
# Auth scheme switch (P7.4)
# ---------------------------------------------------------------------------


def test_jwt_scheme_emits_bearer_token_instead_of_hmac_headers() -> None:
    http = FakeHttp([FakeResponse(status_code=200, body={"irn": "JWT-OK"})])
    client = NRSClient(
        base_url="https://api.nrs.gov.ng/v1",
        credentials=CREDS,
        http=http,
        sleep=lambda _s: None,
        now_factory=lambda: "2026-04-22T10:00:00.000Z",
        auth_scheme="jwt",
        jwt_algorithm="HS256",
        jwt_private_key="jwt-shared-secret",
        jwt_issuer="mai-filer",
    )
    client.submit_filing({"tax_year": 2026})
    headers = http.calls[0]["headers"]
    # HMAC header is absent; Bearer token present.
    assert "X-API-Signature" not in headers
    assert headers["Authorization"].startswith("Bearer ")
    # And the payload binding claim in the token matches what was sent.
    import hashlib

    import jwt as pyjwt

    token = headers["Authorization"].removeprefix("Bearer ").strip()
    claims = pyjwt.decode(
        token,
        "jwt-shared-secret",
        algorithms=["HS256"],
        audience="https://api.nrs.gov.ng/v1",
    )
    payload = http.calls[0]["content"].decode("utf-8")
    assert claims["sha256"] == hashlib.sha256(payload.encode("utf-8")).hexdigest()
