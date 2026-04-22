"""Claude Vision extractor for Mai Filer documents.

v1 kinds: **payslip**, **bank_statement**, **receipt**. CAC certificate
lands later. Each kind defines a forced-tool extraction so Claude's
output conforms to a Pydantic schema — no free-text parsing, no silent
guessing.

One real client (`RealAnthropicVisionClient`) and a `VisionClient`
Protocol for tests. The `VisionExtractor` facade dispatches by kind.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

from anthropic import Anthropic
from pydantic import BaseModel

from app.config import get_settings
from app.documents.schemas import (
    BankStatementExtraction,
    PayslipExtraction,
    ReceiptExtraction,
)

# ---------------------------------------------------------------------------
# Per-kind tool definitions
# ---------------------------------------------------------------------------

PAYSLIP_TOOL_NAME = "submit_payslip_extraction"
BANK_STATEMENT_TOOL_NAME = "submit_bank_statement_extraction"
RECEIPT_TOOL_NAME = "submit_receipt_extraction"


_PAYSLIP_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "employer_name": {"type": ["string", "null"]},
        "employee_name": {"type": ["string", "null"]},
        "period_start": {"type": ["string", "null"], "description": "ISO-8601 date."},
        "period_end": {"type": ["string", "null"]},
        "pay_frequency": {
            "type": "string",
            "enum": ["monthly", "biweekly", "weekly", "annual", "unknown"],
        },
        "gross_income": {"type": "number"},
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

_BANK_STATEMENT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bank_name": {"type": ["string", "null"]},
        "account_holder_name": {"type": ["string", "null"]},
        "account_number_last4": {
            "type": ["string", "null"],
            "description": "Last four digits only. Never include the full account number.",
            "maxLength": 4,
        },
        "statement_period_start": {"type": ["string", "null"]},
        "statement_period_end": {"type": ["string", "null"]},
        "currency": {"type": "string"},
        "opening_balance": {"type": ["number", "null"]},
        "closing_balance": {"type": ["number", "null"]},
        "total_credits": {"type": "number"},
        "total_debits": {"type": "number"},
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": ["string", "null"]},
                    "description": {"type": "string"},
                    "direction": {"type": "string", "enum": ["credit", "debit"]},
                    "amount": {"type": "number"},
                    "balance_after": {"type": ["number", "null"]},
                    "category": {
                        "type": "string",
                        "enum": [
                            "salary",
                            "business_income",
                            "rent_received",
                            "pension_contribution",
                            "nhis_contribution",
                            "nhf_contribution",
                            "tax_payment",
                            "transfer",
                            "fee",
                            "utility",
                            "other",
                        ],
                    },
                },
                "required": ["description", "direction", "amount"],
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["total_credits", "total_debits"],
}

_RECEIPT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "vendor_name": {"type": ["string", "null"]},
        "vendor_tin": {"type": ["string", "null"]},
        "receipt_number": {"type": ["string", "null"]},
        "issue_date": {"type": ["string", "null"]},
        "currency": {"type": "string"},
        "subtotal": {"type": ["number", "null"]},
        "vat_amount": {"type": ["number", "null"]},
        "total_amount": {"type": "number"},
        "receipt_type": {
            "type": "string",
            "enum": [
                "purchase",
                "service",
                "utility",
                "rent",
                "insurance",
                "medical",
                "donation",
                "tax_payment",
                "other",
            ],
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "total": {"type": "number"},
                },
                "required": ["description", "total"],
            },
        },
        "likely_tax_deductible": {"type": ["boolean", "null"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "notes": {"type": ["string", "null"]},
    },
    "required": ["total_amount"],
}


_PAYSLIP_TOOL = {
    "name": PAYSLIP_TOOL_NAME,
    "description": (
        "Submit the structured extraction for a Nigerian payslip. You MUST "
        "call this tool exactly once. Amounts are Nigerian naira. If a "
        "field is unreadable, set it to null rather than guessing. Set "
        "confidence to your own estimate in [0, 1]."
    ),
    "input_schema": _PAYSLIP_INPUT_SCHEMA,
}

_BANK_STATEMENT_TOOL = {
    "name": BANK_STATEMENT_TOOL_NAME,
    "description": (
        "Submit the structured extraction for a Nigerian bank statement. "
        "You MUST call this tool exactly once. Include every transaction in "
        "order. NEVER include the full account number — only the last four "
        "digits. Amounts are in the statement's currency (default NGN). "
        "Categorize each transaction using the provided enum."
    ),
    "input_schema": _BANK_STATEMENT_INPUT_SCHEMA,
}

_RECEIPT_TOOL = {
    "name": RECEIPT_TOOL_NAME,
    "description": (
        "Submit the structured extraction for a Nigerian receipt or invoice. "
        "You MUST call this tool exactly once. Identify the receipt_type "
        "using the enum. Set likely_tax_deductible based on whether the "
        "category typically supports a PIT relief or business deduction — "
        "this is a hint, not a legal determination."
    ),
    "input_schema": _RECEIPT_INPUT_SCHEMA,
}

PAYSLIP_INSTRUCTION = (
    "You are a Nigerian payslip-reading specialist. Extract every relevant "
    f"figure from the document, then call the `{PAYSLIP_TOOL_NAME}` tool "
    "exactly once. Do not include any prose — only the tool call. If a "
    "value is not legible, set it to null and lower your confidence."
)

BANK_STATEMENT_INSTRUCTION = (
    "You are a Nigerian bank-statement-reading specialist. Extract every "
    f"transaction in order, then call the `{BANK_STATEMENT_TOOL_NAME}` tool "
    "exactly once. Do not include any prose — only the tool call. Mask "
    "account numbers — emit only the last four digits. If a value is not "
    "legible, set it to null and lower your confidence."
)

RECEIPT_INSTRUCTION = (
    "You are a Nigerian receipt / invoice reading specialist. Extract every "
    f"line item, then call the `{RECEIPT_TOOL_NAME}` tool exactly once. Do "
    "not include any prose — only the tool call. If a value is not legible, "
    "set it to null and lower your confidence."
)


@dataclass
class ExtractionUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass
class ExtractionRaw:
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
            max_tokens=2048,
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


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------


class VisionExtractor:
    """Dispatch by document kind. Each extractor returns (Pydantic, usage)."""

    def __init__(self, client: VisionClient, model: str) -> None:
        self._client = client
        self._model = model

    def _run(
        self,
        *,
        tool: dict[str, Any],
        instruction: str,
        schema_cls: type[BaseModel],
        file_bytes: bytes,
        content_type: str,
        filename: str | None,
    ) -> tuple[BaseModel, ExtractionUsage]:
        data_b64 = base64.b64encode(file_bytes).decode("ascii")
        raw = self._client.extract_with_tool(
            model=self._model,
            tool=tool,
            instruction=instruction,
            content_type=content_type,
            data_b64=data_b64,
            filename=filename,
        )
        return schema_cls.model_validate(raw.tool_input), raw.usage

    def extract_payslip(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ) -> tuple[PayslipExtraction, ExtractionUsage]:
        pyd, usage = self._run(
            tool=_PAYSLIP_TOOL,
            instruction=PAYSLIP_INSTRUCTION,
            schema_cls=PayslipExtraction,
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        )
        assert isinstance(pyd, PayslipExtraction)
        return pyd, usage

    def extract_bank_statement(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ) -> tuple[BankStatementExtraction, ExtractionUsage]:
        pyd, usage = self._run(
            tool=_BANK_STATEMENT_TOOL,
            instruction=BANK_STATEMENT_INSTRUCTION,
            schema_cls=BankStatementExtraction,
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        )
        assert isinstance(pyd, BankStatementExtraction)
        return pyd, usage

    def extract_receipt(
        self, *, file_bytes: bytes, content_type: str, filename: str | None = None
    ) -> tuple[ReceiptExtraction, ExtractionUsage]:
        pyd, usage = self._run(
            tool=_RECEIPT_TOOL,
            instruction=RECEIPT_INSTRUCTION,
            schema_cls=ReceiptExtraction,
            file_bytes=file_bytes,
            content_type=content_type,
            filename=filename,
        )
        assert isinstance(pyd, ReceiptExtraction)
        return pyd, usage


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
