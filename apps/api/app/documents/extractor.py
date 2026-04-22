"""Claude Vision extractor for Mai Filer documents.

Phase 3 v1 scope: payslips. Other kinds (receipts, bank statements, CAC)
reuse the same pattern with different schemas.

Approach: ask Claude Sonnet 4.6 (vision-capable, cheaper than Opus for
tool-structured work) to read the uploaded file and call a single forced
tool — `submit_payslip_extraction` — whose input schema matches our
`PayslipExtraction` Pydantic model. Forcing the tool guarantees structured
output; parsing failures raise and are surfaced to the user rather than
silently swallowed (per the project's "don't invent, don't guess" rule).

The real vision client and the fake used in tests both implement
`VisionClient` so tool-loop plumbing stays simple.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

from anthropic import Anthropic

from app.config import get_settings
from app.documents.schemas import PayslipExtraction


PAYSLIP_TOOL_NAME = "submit_payslip_extraction"

_PAYSLIP_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "employer_name": {"type": ["string", "null"]},
        "employee_name": {"type": ["string", "null"]},
        "period_start": {
            "type": ["string", "null"],
            "description": "ISO-8601 date, e.g. 2026-03-01",
        },
        "period_end": {"type": ["string", "null"]},
        "pay_frequency": {
            "type": "string",
            "enum": ["monthly", "biweekly", "weekly", "annual", "unknown"],
        },
        "gross_income": {
            "type": "number",
            "description": "Gross pay for the period, in Nigerian naira.",
        },
        "paye_withheld": {"type": "number"},
        "pension_contribution": {"type": "number"},
        "nhis_contribution": {"type": "number"},
        "cra_amount": {"type": ["number", "null"]},
        "net_pay": {"type": ["number", "null"]},
        "other_earnings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "amount": {"type": "number"},
                    "category": {"type": "string", "enum": ["earning", "deduction"]},
                },
                "required": ["label", "amount"],
            },
        },
        "other_deductions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "amount": {"type": "number"},
                    "category": {"type": "string", "enum": ["earning", "deduction"]},
                },
                "required": ["label", "amount"],
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["gross_income", "pay_frequency"],
}

_PAYSLIP_TOOL = {
    "name": PAYSLIP_TOOL_NAME,
    "description": (
        "Submit the structured extraction for a Nigerian payslip. You MUST "
        "call this tool exactly once per payslip. Amounts are Nigerian naira. "
        "If a field is unreadable, set it to null rather than guessing. Set "
        "confidence to your own estimate in [0, 1]."
    ),
    "input_schema": _PAYSLIP_INPUT_SCHEMA,
}

PAYSLIP_INSTRUCTION = (
    "You are a Nigerian payslip-reading specialist. Extract every relevant "
    "figure from the document. Then call the `submit_payslip_extraction` "
    "tool exactly once. Do not include any prose — only the tool call. If a "
    "value is not legible, set it to null and lower your confidence."
)


@dataclass
class ExtractionUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class ExtractionRaw:
    """Output of a vision extraction round-trip: the tool input plus usage."""

    tool_input: dict[str, Any]
    usage: ExtractionUsage


class VisionClient(Protocol):
    def extract_with_tool(
        self,
        *,
        model: str,
        tool: dict[str, Any],
        instruction: str,
        content_type: str,
        data_b64: str,
        filename: str | None = None,
    ) -> ExtractionRaw:
        ...


class RealAnthropicVisionClient:
    """Anthropic SDK adapter that sends image/PDF content and forces a tool call."""

    def __init__(self, api_key: str) -> None:
        self._client = Anthropic(api_key=api_key)

    def extract_with_tool(
        self,
        *,
        model: str,
        tool: dict[str, Any],
        instruction: str,
        content_type: str,
        data_b64: str,
        filename: str | None = None,
    ) -> ExtractionRaw:
        if content_type == "application/pdf":
            source = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": data_b64,
                },
            }
        else:
            source = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": content_type,
                    "data": data_b64,
                },
            }

        response = self._client.messages.create(
            model=model,
            max_tokens=1024,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[
                {
                    "role": "user",
                    "content": [
                        source,
                        {"type": "text", "text": instruction},
                    ],
                }
            ],
        )

        tool_input: dict[str, Any] | None = None
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                tool_input = dict(block.input)
                break
        if tool_input is None:
            raise RuntimeError("vision extraction did not return a tool_use block")

        usage = ExtractionUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(
                response.usage, "cache_creation_input_tokens", 0
            )
            or 0,
        )
        return ExtractionRaw(tool_input=tool_input, usage=usage)


class VisionExtractor:
    """Facade used by the document service. Owns the vision client and model."""

    def __init__(self, client: VisionClient, model: str) -> None:
        self._client = client
        self._model = model

    def extract_payslip(
        self,
        *,
        file_bytes: bytes,
        content_type: str,
        filename: str | None = None,
    ) -> tuple[PayslipExtraction, ExtractionUsage]:
        data_b64 = base64.b64encode(file_bytes).decode("ascii")
        raw = self._client.extract_with_tool(
            model=self._model,
            tool=_PAYSLIP_TOOL,
            instruction=PAYSLIP_INSTRUCTION,
            content_type=content_type,
            data_b64=data_b64,
            filename=filename,
        )
        extraction = PayslipExtraction.model_validate(raw.tool_input)
        return extraction, raw.usage


def build_default_vision_extractor() -> VisionExtractor:
    settings = get_settings()
    client: VisionClient = RealAnthropicVisionClient(api_key=settings.anthropic_api_key)
    return VisionExtractor(client=client, model=settings.claude_model_tools)


# ---------------------------------------------------------------------------
# DI helpers
# ---------------------------------------------------------------------------

_default_extractor: VisionExtractor | None = None


def set_default_vision_extractor(extractor: VisionExtractor) -> None:
    global _default_extractor
    _default_extractor = extractor


def get_default_vision_extractor() -> VisionExtractor:
    global _default_extractor
    if _default_extractor is None:
        _default_extractor = build_default_vision_extractor()
    return _default_extractor
