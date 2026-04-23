"""Mai Filer tool registry + orchestrator tool-loop smoke tests (P2.9, P3.8)."""

from __future__ import annotations

import json
from collections.abc import Iterator

from app.agents.mai_filer.orchestrator import (
    AgentTurn,
    AnthropicUsage,
    MaiFilerOrchestrator,
    StreamResult,
    ToolCall,
)
from app.agents.mai_filer.schemas import ChatRequest
from app.agents.mai_filer.tools import TOOLS, run_tool, tool_names, tool_schemas
from app.db.models import Document, Filing
from app.documents.storage import InMemoryStorage, set_default_storage


def test_tool_registry_exposes_expected_tools() -> None:
    names = tool_names()
    for expected in [
        "calc_pit",
        "calc_paye",
        "explore_reliefs",
        "calc_vat",
        "check_vat_registrable",
        "calc_dev_levy",
        "list_recent_documents",
        "read_document_extraction",
        "audit_filing",
        "prepare_filing_pack",
        "list_recent_filings",
        "verify_identity",
        "submit_to_nrs",
        "calc_cit",
        "calc_wht",
        "list_wht_classes",
        "validate_ubl_envelope",
        "list_user_facts",
        "recall_memory",
        "detect_yoy_anomalies",
        "suggest_mid_year_nudges",
        "list_ngo_exempt_purposes",
        "audit_ngo_filing",
        "audit_ngo_return",
    ]:
        assert expected in names, f"missing tool: {expected}"


def test_tool_schemas_are_well_formed() -> None:
    schemas = tool_schemas()
    for schema in schemas:
        assert {"name", "description", "input_schema"} <= set(schema)
        assert schema["input_schema"]["type"] == "object"
        assert isinstance(schema["input_schema"].get("properties"), dict)


def test_run_tool_calc_pit_returns_correct_total() -> None:
    payload = json.loads(run_tool("calc_pit", {"annual_income": 5_000_000}))
    assert payload["total_tax"] == "690000.00"
    # Six bands in the breakdown with band 1 exempting 800k.
    assert len(payload["bands"]) == 6
    assert payload["bands"][0]["rate"] == "0.00"


def test_run_tool_calc_paye_with_deductions() -> None:
    payload = json.loads(
        run_tool(
            "calc_paye",
            {
                "annual_gross": 5_000_000,
                "pension": 400_000,
                "nhis": 75_000,
                "cra": 1_200_000,
            },
        )
    )
    assert payload["annual_tax"] == "388500.00"
    assert payload["monthly_tax"] == "32375.00"


def test_run_tool_check_vat_registrable() -> None:
    payload = json.loads(run_tool("check_vat_registrable", {"annual_turnover": 120_000_000}))
    assert payload["is_registrable"] is True
    assert payload["distance_to_threshold"] == "-20000000.00"


def test_run_tool_unknown_name_returns_error_payload() -> None:
    payload = json.loads(run_tool("does_not_exist", {}))
    assert "error" in payload


def test_run_tool_input_validation_error_bubbles_up() -> None:
    payload = json.loads(run_tool("calc_pit", {"annual_income": -1}))
    assert "error" in payload


def test_tool_registry_keeps_calc_pit_schema_stable() -> None:
    # Stability guard: Claude's prompt caches reference the exact schema.
    schema = next(t for t in TOOLS if t.name == "calc_pit")
    assert schema.input_schema == {
        "type": "object",
        "properties": {
            "annual_income": {
                "type": "number",
                "description": "Annual income in Nigerian naira (₦). Must be >= 0.",
            }
        },
        "required": ["annual_income"],
    }


# ---------------------------------------------------------------------------
# Orchestrator tool-use loop smoke
# ---------------------------------------------------------------------------


class ScriptedAnthropic:
    """Plays a fixed script of AgentTurns. Records what it sees."""

    def __init__(self, turns: list[AgentTurn]) -> None:
        self._turns = list(turns)
        self.calls: list[dict] = []

    def messages_create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: list[dict],
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AgentTurn:
        self.calls.append(
            {"model": model, "system": system, "messages": messages, "tools": tools}
        )
        if not self._turns:
            return AgentTurn(text="(no more turns)", tool_calls=[], stop_reason="end_turn",
                             usage=AnthropicUsage())
        return self._turns.pop(0)

    def messages_stream(
        self, *, model: str, max_tokens: int, system: list[dict], messages: list[dict]
    ) -> Iterator[str | StreamResult]:
        # Unused in these tests.
        yield StreamResult(text="", usage=AnthropicUsage())


def test_orchestrator_executes_tool_and_loops_back() -> None:
    """
    Turn 1: Claude says 'let me calculate' and invokes calc_pit.
    Turn 2: Claude returns the final explanation text, stop_reason=end_turn.

    We assert:
      - Two Claude calls happened.
      - The second call carried both the assistant tool_use block and the
        user tool_result block.
      - The tool_result content contains the computed total_tax.
      - The final ChatResponse.message is Claude's turn-2 text.
    """
    first_turn = AgentTurn(
        text="Let me calculate that for you.",
        tool_calls=[
            ToolCall(
                id="toolu_1",
                name="calc_pit",
                input={"annual_income": 5_000_000},
            )
        ],
        stop_reason="tool_use",
        usage=AnthropicUsage(input_tokens=300, output_tokens=40),
    )
    second_turn = AgentTurn(
        text=(
            "Your 2026 PIT on ₦5,000,000 is ₦690,000. That's ₦0 on the first "
            "₦800,000 (exempt), ₦330,000 at 15% on the next ₦2,200,000, and "
            "₦360,000 at 18% on the remaining ₦2,000,000. Effective rate ≈ 13.8%."
        ),
        tool_calls=[],
        stop_reason="end_turn",
        usage=AnthropicUsage(input_tokens=450, output_tokens=90),
    )
    client = ScriptedAnthropic([first_turn, second_turn])
    orchestrator = MaiFilerOrchestrator(client=client, model="claude-opus-4-7")

    response = orchestrator.chat(
        ChatRequest(message="I earn ₦5,000,000 a year. What's my PIT?", language="en")
    )

    assert len(client.calls) == 2
    # Second call's history must include the tool_use and tool_result blocks.
    second_call_messages = client.calls[1]["messages"]
    # [user, assistant(tool_use), user(tool_result)]
    assert len(second_call_messages) == 3
    assistant_blocks = second_call_messages[1]["content"]
    assert any(b["type"] == "tool_use" and b["name"] == "calc_pit" for b in assistant_blocks)
    tool_result_blocks = second_call_messages[2]["content"]
    assert tool_result_blocks[0]["type"] == "tool_result"
    result_payload = json.loads(tool_result_blocks[0]["content"])
    assert result_payload["total_tax"] == "690000.00"

    # Final response text is Claude's turn-2 output.
    assert "₦690,000" in response.message
    # Usage is accumulated across turns.
    assert response.input_tokens == 750
    assert response.output_tokens == 130


def test_orchestrator_skips_tool_loop_when_claude_ends_turn_directly() -> None:
    turn = AgentTurn(
        text="Hello, I'm Mai Filer. How can I help?",
        tool_calls=[],
        stop_reason="end_turn",
        usage=AnthropicUsage(input_tokens=120, output_tokens=20),
    )
    client = ScriptedAnthropic([turn])
    orchestrator = MaiFilerOrchestrator(client=client, model="claude-opus-4-7")

    response = orchestrator.chat(ChatRequest(message="Hi Mai", language="en"))
    assert len(client.calls) == 1
    assert response.message.startswith("Hello, I'm Mai Filer.")


def test_list_recent_documents_tool_reads_db(db_session, override_db) -> None:
    """P3.8 — the Mai tool sees documents the user uploaded."""
    session = db_session
    session.add(
        Document(
            id="doc-1",
            filename="march.png",
            content_type="image/png",
            size_bytes=1000,
            storage_key="mem/foo",
            kind="payslip",
            extraction_json={"gross_income": 420000, "pay_frequency": "monthly"},
        )
    )
    session.commit()

    payload = json.loads(run_tool("list_recent_documents", {"limit": 5}))
    assert len(payload["documents"]) == 1
    item = payload["documents"][0]
    assert item["id"] == "doc-1"
    assert item["kind"] == "payslip"
    assert item["has_extraction"] is True


def test_read_document_extraction_tool_returns_payload(db_session, override_db) -> None:
    session = db_session
    session.add(
        Document(
            id="doc-2",
            filename="march.pdf",
            content_type="application/pdf",
            size_bytes=1234,
            storage_key="mem/bar",
            kind="payslip",
            extraction_json={"gross_income": 420000, "pay_frequency": "monthly"},
        )
    )
    session.commit()

    payload = json.loads(run_tool("read_document_extraction", {"document_id": "doc-2"}))
    assert payload["id"] == "doc-2"
    assert payload["extraction"]["gross_income"] == 420000


def test_read_document_extraction_tool_handles_missing_id(override_db) -> None:
    payload = json.loads(
        run_tool("read_document_extraction", {"document_id": "nope"})
    )
    assert "error" in payload


# ---------------------------------------------------------------------------
# Filing tools (Phase 4)
# ---------------------------------------------------------------------------


def _green_return_dict() -> dict:
    from datetime import date
    from decimal import Decimal

    from app.filing.schemas import IncomeSource, PITReturn, TaxpayerIdentity

    return PITReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        taxpayer=TaxpayerIdentity(
            nin="12345678901",
            full_name="Chidi Okafor",
            residential_address="1 Ikoyi Crescent",
        ),
        income_sources=[
            IncomeSource(
                kind="employment",
                payer_name="Globacom Ltd",
                gross_amount=Decimal("5000000"),
                tax_withheld=Decimal("650000"),
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
            )
        ],
        declaration=True,
    ).model_dump(mode="json")


def test_audit_filing_tool_returns_green_for_valid_return(db_session, override_db) -> None:
    filing = Filing(
        id="f-1",
        tax_year=2026,
        return_json=_green_return_dict(),
        audit_status="pending",
    )
    db_session.add(filing)
    db_session.commit()
    payload = json.loads(run_tool("audit_filing", {"filing_id": "f-1"}))
    assert payload["status"] == "green"
    assert payload["findings"] == []


def test_audit_filing_tool_handles_missing_filing(override_db) -> None:
    payload = json.loads(run_tool("audit_filing", {"filing_id": "nope"}))
    assert "error" in payload


def test_prepare_filing_pack_tool_green_path(db_session, override_db) -> None:
    set_default_storage(InMemoryStorage())
    try:
        filing = Filing(
            id="f-2",
            tax_year=2026,
            return_json=_green_return_dict(),
            audit_status="pending",
        )
        db_session.add(filing)
        db_session.commit()
        payload = json.loads(run_tool("prepare_filing_pack", {"filing_id": "f-2"}))
        assert payload.get("audit_status") == "green"
        assert payload["download_urls"]["pdf"].endswith("/pack.pdf")
        assert payload["download_urls"]["json"].endswith("/pack.json")
        assert payload["settlement"]["net_payable"] == "40000.00"
    finally:
        set_default_storage(InMemoryStorage())  # reset


def test_prepare_filing_pack_tool_refuses_red_audit(db_session, override_db) -> None:
    set_default_storage(InMemoryStorage())
    try:
        bad = _green_return_dict()
        bad["declaration"] = False
        filing = Filing(
            id="f-3",
            tax_year=2026,
            return_json=bad,
            audit_status="pending",
        )
        db_session.add(filing)
        db_session.commit()
        payload = json.loads(run_tool("prepare_filing_pack", {"filing_id": "f-3"}))
        assert "error" in payload
        assert payload.get("audit_status") == "red"
    finally:
        set_default_storage(InMemoryStorage())


def test_verify_identity_tool_happy_path(db_session, override_db, monkeypatch) -> None:
    """P5.9 — verify_identity tool invokes the identity service and returns
    a JSON-safe result dict with verified + name_match status."""
    from tests.test_identity_service import ScriptedAggregator, _happy_verification
    from app.identity.service import IdentityService

    def _fake_build(session):
        return IdentityService(
            aggregator=ScriptedAggregator([_happy_verification()]),
            session=session,
            hash_salt="tool-salt",
            vault_key="tool-vault-key-long-enough",
            sleep=lambda _s: None,
        )

    monkeypatch.setattr(
        "app.agents.mai_filer.tools.build_identity_service", _fake_build
    )
    payload = json.loads(
        run_tool(
            "verify_identity",
            {
                "nin": "12345678901",
                "consent": True,
                "declared_name": "Chidi Okafor",
            },
        )
    )
    assert payload["verified"] is True
    assert payload["full_name"] == "Chidi Emeka Okafor"
    assert payload["name_match_status"] == "fuzzy"
    assert payload["consent_log_id"]


def test_verify_identity_tool_refuses_without_consent(override_db) -> None:
    payload = json.loads(
        run_tool("verify_identity", {"nin": "12345678901", "consent": False})
    )
    assert "error" in payload
    assert payload.get("reason") == "consent_required"


def test_calc_cit_tool_flags_placeholder_statutory() -> None:
    """P9 — calc_cit tool surfaces that the 2026 CIT table is still a placeholder."""
    payload = json.loads(
        run_tool(
            "calc_cit",
            {"annual_turnover": 80_000_000, "assessable_profit": 10_000_000},
        )
    )
    assert payload["tier"] in {"small", "medium", "large"}
    assert payload["cit_amount"] is not None
    assert payload["statutory_is_placeholder"] is True
    assert "PLACEHOLDER" in payload["statutory_source"]


def test_calc_wht_tool_happy_path() -> None:
    payload = json.loads(
        run_tool(
            "calc_wht",
            {"gross_amount": 1_000_000, "transaction_class": "rent"},
        )
    )
    assert payload["wht_amount"] is not None
    assert payload["statutory_is_placeholder"] is True


def test_calc_wht_tool_unknown_class_returns_error() -> None:
    payload = json.loads(
        run_tool(
            "calc_wht",
            {"gross_amount": 1_000, "transaction_class": "made_up"},
        )
    )
    assert "error" in payload
    assert "known_classes" in payload
    assert "rent" in payload["known_classes"]


def test_list_wht_classes_tool() -> None:
    payload = json.loads(run_tool("list_wht_classes", {}))
    assert "classes" in payload
    assert "rent" in payload["classes"]


def test_validate_ubl_envelope_tool_flags_missing_fields() -> None:
    """An empty envelope fails validation with structural errors."""
    payload = json.loads(
        run_tool(
            "validate_ubl_envelope",
            {"envelope": {"version": "ubl-3.0", "sections": []}},
        )
    )
    assert payload["ok"] is False
    assert payload["statutory_is_placeholder"] is True
    codes = {f["code"] for f in payload["findings"]}
    assert "UBL-SECTION-COUNT" in codes


def test_memory_tools_round_trip_via_registry(db_session, override_db) -> None:
    """P8.9 — record a fact through the repository, then recall it via the
    Mai tool surface."""
    from app.memory.facts import record_fact
    from decimal import Decimal as D

    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2025,
        fact_type="annual_gross_income",
        value=D("5000000"),
        label="2025 gross",
    )
    record_fact(
        db_session,
        user_nin_hash="h",
        tax_year=2026,
        fact_type="annual_gross_income",
        value=D("10000000"),
        label="2026 gross",
    )
    db_session.commit()

    # list_user_facts.
    facts = json.loads(run_tool("list_user_facts", {"nin_hash": "h"}))
    assert len(facts["facts"]) == 2

    # recall_memory.
    hits = json.loads(run_tool("recall_memory", {"query": "gross", "nin_hash": "h"}))
    assert len(hits["facts"]) >= 1

    # detect_yoy_anomalies — 100% jump between 2025 and 2026.
    anomalies = json.loads(
        run_tool(
            "detect_yoy_anomalies",
            {"current_year": 2026, "nin_hash": "h"},
        )
    )
    assert len(anomalies["findings"]) == 1
    assert anomalies["findings"][0]["severity"] == "alert"

    # suggest_mid_year_nudges — approaching VAT threshold.
    nudges = json.loads(
        run_tool(
            "suggest_mid_year_nudges",
            {
                "current_year": 2026,
                "ytd_gross": 42_000_000,
                "month": 6,
                "nin_hash": "h",
            },
        )
    )
    codes = {n["code"] for n in nudges["nudges"]}
    assert "VAT_THRESHOLD_APPROACH" in codes


def test_list_ngo_exempt_purposes_surfaces_placeholder() -> None:
    payload = json.loads(run_tool("list_ngo_exempt_purposes", {}))
    assert "charitable" in payload["purposes"]
    assert payload["statutory_is_placeholder"] is True


def test_audit_ngo_return_tool_green_path() -> None:
    from datetime import date
    from decimal import Decimal as D

    from app.filing.ngo_schemas import (
        NGOExpenditureBlock,
        NGOIncomeBlock,
        NGOReturn,
        Organization,
        WHTScheduleRow,
    )

    return_dict = NGOReturn(
        tax_year=2026,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        organization=Organization(
            cac_part_c_rc="IT-555000",
            legal_name="Exempt Body",
            purpose="charitable",
        ),
        income=NGOIncomeBlock(local_donations=D("2000000")),
        expenditure=NGOExpenditureBlock(program_expenses=D("1500000")),
        wht_schedule=[
            WHTScheduleRow(
                period_month=2,
                transaction_class="rent",
                recipient_category="corporate",
                gross_amount=D("500000"),
                wht_amount=D("50000"),
            )
        ],
        supporting_document_ids=["doc-1"],
        exemption_status_declaration=True,
        declaration=True,
    ).model_dump(mode="json")
    payload = json.loads(run_tool("audit_ngo_return", {"return_": return_dict}))
    assert payload["status"] == "green"
    assert payload["statutory_is_placeholder"] is True


def test_audit_ngo_filing_tool_rejects_wrong_tax_kind(db_session, override_db) -> None:
    """Guard against using the NGO auditor on a PIT filing."""
    filing = Filing(
        id="wrong-kind",
        tax_year=2026,
        tax_kind="pit",
        return_json={},
        audit_status="pending",
    )
    db_session.add(filing)
    db_session.commit()
    payload = json.loads(
        run_tool("audit_ngo_filing", {"filing_id": "wrong-kind"})
    )
    assert "error" in payload
    assert payload["reason"] == "tax_kind_mismatch"


def test_submit_to_nrs_tool_simulates_without_creds(db_session, override_db) -> None:
    """P6 — submit_to_nrs tool returns a simulated outcome when NRS env
    credentials are absent (default in tests)."""
    set_default_storage(InMemoryStorage())
    filing = Filing(
        id="f-nrs-1",
        tax_year=2026,
        return_json=_green_return_dict(),
        audit_status="green",
    )
    db_session.add(filing)
    db_session.commit()

    payload = json.loads(run_tool("submit_to_nrs", {"filing_id": "f-nrs-1"}))
    assert payload["status"] == "simulated"
    assert payload["simulated"] is True
    assert payload["irn"].startswith("SIM-IRN-")


def test_submit_to_nrs_tool_refuses_not_ready(db_session, override_db) -> None:
    filing = Filing(
        id="f-nrs-2",
        tax_year=2026,
        return_json=_green_return_dict(),
        audit_status="pending",  # not audited yet
    )
    db_session.add(filing)
    db_session.commit()

    payload = json.loads(run_tool("submit_to_nrs", {"filing_id": "f-nrs-2"}))
    assert "error" in payload
    assert payload["reason"] == "not_ready_for_submission"


def test_list_recent_filings_tool(db_session, override_db) -> None:
    db_session.add(
        Filing(
            id="f-4",
            tax_year=2026,
            return_json=_green_return_dict(),
            audit_status="green",
        )
    )
    db_session.commit()
    payload = json.loads(run_tool("list_recent_filings", {"limit": 5}))
    assert len(payload["filings"]) == 1
    assert payload["filings"][0]["id"] == "f-4"
    assert payload["filings"][0]["audit_status"] == "green"


def test_orchestrator_respects_tool_turn_cap() -> None:
    """If Claude keeps asking for tools, the loop halts after MAX_TOOL_TURNS."""
    looping_turn = AgentTurn(
        text="",
        tool_calls=[ToolCall(id="t", name="calc_pit", input={"annual_income": 1})],
        stop_reason="tool_use",
        usage=AnthropicUsage(),
    )
    client = ScriptedAnthropic([looping_turn] * 20)
    orchestrator = MaiFilerOrchestrator(client=client, model="claude-opus-4-7")

    orchestrator.chat(ChatRequest(message="loop", language="en"))
    # The loop caps at MAX_TOOL_TURNS total calls when every turn is tool_use.
    from app.agents.mai_filer.orchestrator import MAX_TOOL_TURNS

    assert len(client.calls) == MAX_TOOL_TURNS
