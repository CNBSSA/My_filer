# Mai Filer — Roadmap (Smallest-Task Breakdown)

> Every task below is sized so it can be executed, tested, and committed on
> its own. Each task has an ID (`P{phase}.{n}`) so the user can reference any
> one step ("do P2.3 next"). Statuses: `[ ]` pending · `[~]` in progress ·
> `[x]` done · `[!]` blocked.
>
> **v1 scope reflects the locked ADRs** (`docs/DECISIONS.md`): individual
> (PAYE / PIT) first, Dojah as default aggregator, English + Hausa + Yoruba +
> Igbo + Pidgin from v1.

---

## PHASE 0 — Foundation ✅ COMPLETE

Goal: clean monorepo, CLAUDE.md memory anchor, docs locked, dev env boots.

- [x] **P0.1** — Write `CLAUDE.md` memory anchor
- [x] **P0.2** — Write `docs/KNOWLEDGE_BASE.md`
- [x] **P0.3** — Write `docs/ROLES.md`
- [x] **P0.4** — Write `docs/ARCHITECTURE.md`
- [x] **P0.5** — Write `docs/COMPLIANCE.md`
- [x] **P0.6** — Write `docs/ROADMAP.md`
- [x] **P0.7** — Write `docs/MASTER_PLAN.md`
- [x] **P0.8** — Create monorepo folders (`apps/api`, `apps/web`, `packages/shared`, `infra/`)
- [x] **P0.9** — Add root `.gitignore`
- [x] **P0.10** — Add root `.env.example`
- [x] **P0.11** — Add root `README.md`
- [x] **P0.12** — Create `apps/api/pyproject.toml`
- [x] **P0.13** — Create `apps/api/app/main.py` with `/health`
- [x] **P0.14** — Create `apps/api/app/config.py` with typed settings
- [x] **P0.15** — Create `apps/api/tests/test_health.py` (green)
- [x] **P0.16** — Web placeholder (full Next.js scaffold is P1.10)
- [x] **P0.17** — Add `docker-compose.yml` (Postgres 16, Redis 7, MinIO)
- [x] **P0.18** — First commit + push
- [x] **P0.19** — Write `docs/DECISIONS.md` (ADR-0001..0004)

## PHASE 1 — Mai Filer Core (Agent + Multilingual v1)

Goal: live chat with in-role Mai Filer, streaming, persisted, and speaking
the user's chosen Nigerian language.

### 1a. Agent backbone

- [ ] **P1.1** — Install `anthropic` SDK in `apps/api`
- [ ] **P1.2** — Expand `apps/api/app/agents/mai_filer/prompt.py` with role doctrine, 2026 tax frame, and conversational style (v1 locked)
- [ ] **P1.3** — Create `apps/api/app/agents/mai_filer/orchestrator.py` — Claude client wrapper with prompt caching on the system block
- [ ] **P1.4** — Pydantic schemas in `apps/api/app/agents/mai_filer/schemas.py`: `ChatTurn`, `ChatRequest`, `ChatResponse`, `Language`
- [ ] **P1.5** — `POST /v1/chat` endpoint (non-streaming first)
- [ ] **P1.6** — Unit test chat endpoint with a mocked Anthropic client
- [ ] **P1.7** — `POST /v1/chat/stream` (Server-Sent Events)

### 1b. Persistence

- [ ] **P1.8** — Alembic init; `threads` + `messages` tables (with `language`, `user_id`, `created_at`)
- [ ] **P1.9** — Persist every chat turn; return thread IDs

### 1c. Multilingual (ADR-0004)

- [ ] **P1.10** — `apps/api/app/i18n/` — language registry (en, ha, yo, ig, pcm) and system-prompt addenda per language (tone, greeting conventions, tax-jargon glossary)
- [ ] **P1.11** — `/v1/chat` accepts `language` field; orchestrator injects the matching addendum as an appended system block
- [ ] **P1.12** — Low-confidence translation fallback: if Claude's detected output language drifts, append an English recap
- [ ] **P1.13** — Unit tests — orchestrator picks the right addendum per language

### 1d. Web

- [ ] **P1.14** — `cd apps/web && npx create-next-app@latest . --ts --tailwind --app --src-dir`
- [ ] **P1.15** — `next-intl` install + `messages/{en,ha,yo,ig,pcm}.json` stubs
- [ ] **P1.16** — `/chat` page: message list, input, language selector in header
- [ ] **P1.17** — Wire SSE stream to the UI; render partial tokens
- [ ] **P1.18** — Thread list sidebar; load-by-id
- [ ] **P1.19** — Demo flow: "Hello Mai" in each of en / ha / yo / ig / pcm → Mai introduces herself in that language

## PHASE 2 — Tax Calculator Service (Individual-First) ✅ v1 SLICE COMPLETE

Goal: Mai can compute PIT and PAYE via tool use, explain bands, and propose
legal reliefs.

- [x] **P2.1** — `apps/api/app/tax/pit.py` — `calculate_pit_2026(annual_income: Decimal) -> PITResult` with per-band breakdown
- [x] **P2.2** — PIT unit tests (12 cases: band boundaries, zero, negative, decimal precision)
- [x] **P2.3** — `apps/api/app/tax/paye.py` — PAYE after CRA, pension, NHIS, other reliefs
- [x] **P2.4** — PAYE unit tests (8 cases: no-deductions parity, band-crossing, negative-guard, zero-floor)
- [x] **P2.5** — `apps/api/app/tax/reliefs.py` — `explore_reliefs()` returns baseline + per-scenario projections
- [x] **P2.6** — Relief unit tests (7 cases: topups, boundary hops, additive compounding)
- [x] **P2.7** — Tool wrappers in `agents/mai_filer/tools.py` — `calc_pit`, `calc_paye`, `explore_reliefs`, `calc_vat`, `check_vat_registrable`, `calc_dev_levy`
- [x] **P2.8** — Orchestrator tool-use loop (sync `chat()`) with `MAX_TOOL_TURNS` safety cap
- [x] **P2.9** — Smoke tests: scripted Claude → tool_use → tool_result → final text; 75 tests passing overall
- [x] **P2.10** — `apps/api/app/tax/vat.py` — `calculate_vat()`, `is_vat_registrable()`, `distance_to_threshold()`
- [x] **P2.11** — VAT unit tests (10 cases)
- [ ] **P2.12** — **[blocked — owner input]** `apps/api/app/tax/cit.py` — needs 2026 CIT bands by turnover
- [ ] **P2.13** — **[blocked — owner input]** `apps/api/app/tax/wht.py` — needs 2026 WHT rates per transaction class
- [x] **P2.14** — `apps/api/app/tax/dev_levy.py` — 4% Development Levy (scaffold; full exercise in v2)

## PHASE 3 — Document Intelligence (Payslip First)

Goal: upload a Nigerian payslip, Mai extracts structured data, pre-fills the
PAYE worksheet.

- [x] **P3.1** — `POST /v1/documents` multipart endpoint + GET single + list
- [x] **P3.2** — `StorageAdapter` interface + `InMemoryStorage` + `LocalDiskStorage` (MinIO/S3 adapter deferred to infra phase)
- [x] **P3.3** — `documents/extractor.py` — Claude Sonnet 4.6 Vision wrapper with forced tool-use for structured output
- [x] **P3.4** — Payslip Pydantic schema + `DocumentKind` literal + `DocumentRecord` API response
- [x] **P3.5** — Extractor tests (mocked VisionClient) + endpoint tests (fake extractor, InMemoryStorage)
- [x] **P3.6** — Bank statement schema + extractor. `BankStatementExtraction` with per-transaction direction/category enums; `VisionExtractor.extract_bank_statement()` forces `submit_bank_statement_extraction`; account number stored as last-4 only (NDPR minimization).
- [x] **P3.7** — Receipt schema + extractor. `ReceiptExtraction` with typed receipt_type (insurance, medical, utility, rent, donation, …), items, tax-deductibility hint; forced-tool via `submit_receipt_extraction`.
- [x] **P3.8** — Tool registration: `list_recent_documents` + `read_document_extraction` for Mai
- [x] **P3.9** — Web: upload widget in chat (📎 picker + page-wide drag-and-drop). Uploads via `POST /v1/documents`, then injects a "I just uploaded…" nudge into the conversation so Mai calls `read_document_extraction` + `calc_paye`.
- [x] **P3.10** — End-to-end browser demo documented in `README.md` (run steps). Live Claude calls still require a valid `ANTHROPIC_API_KEY`; the plumbing is verified green by 87 unit tests.

## PHASE 4 — Filing Pack Generator (Individual Path) ✅ BACKEND COMPLETE

Goal: generate a downloadable, NRS-compliant PIT / PAYE pack for manual
submission.

- [x] **P4.1** — PIT / PAYE return schema in `apps/api/app/filing/schemas.py` (Pydantic) + `Filing` ORM + alembic 0003
- [x] **P4.2** — `apps/api/app/filing/serialize.py` — canonical JSON pack builder (stable key order, Decimal→string, authoritative recomputation)
- [x] **P4.3** — `apps/api/app/filing/pdf.py` — branded PDF renderer via ReportLab (taxpayer block, income sources table, deductions, PIT bands, settlement, declaration)
- [x] **P4.4** — `apps/api/app/api/filings.py`: POST `/v1/filings` (create), PUT `/{id}` (update), POST `/{id}/audit`, POST `/{id}/pack`, GET `/{id}/pack.pdf`, GET `/{id}/pack.json`
- [x] **P4.5** — `apps/api/app/filing/audit.py` — Audit Shield with 11 v1 checks (NIN, name, tax year, declaration, income, per-source sanity, pension heuristic, deductions vs gross, withheld consistency, recompute check, supporting-doc cross-ref)
- [x] **P4.6** — Green/yellow/red classification with structured `AuditFinding` list (code, severity, message, field_path)
- [x] **P4.7** — Mai Filer tools: `audit_filing`, `prepare_filing_pack` (refuses to finalize a red-status filing), `list_recent_filings`. Registry grew from 8 to 11 tools.
- [x] **P4.8** — Web: `/filings/[id]` review page with Audit Shield summary, run-audit / prepare-pack buttons, taxpayer + computation + sources breakdown, PDF/JSON download links
- [ ] **P4.9** — **[deferred to v2 SME]** UBL 3.0 + 55-field schema — blocked on owner's 55-field list

## PHASE 5 — NIN Verification (Dojah default) ✅ BACKEND COMPLETE

Goal: verified individual identity with NDPR-compliant consent.

- [x] **P5.1** — `identity/base.py` — `IdentityAggregator` Protocol + `NINVerification` dataclass + `AggregatorError` escalation
- [x] **P5.2** — `identity/dojah.py` adapter (default per ADR-0003). `HttpClient` Protocol seam for hermetic tests; 2xx maps to verification, 4xx returns invalid, 5xx / transport raises `AggregatorError`.
- [x] **P5.3** — `identity/seamfix.py` (stub — raises `AggregatorError` until sandbox creds arrive)
- [x] **P5.4** — `identity/prembly.py` (stub — same pattern as Seamfix)
- [x] **P5.5** — `identity/service.py` — `verify_taxpayer()` orchestrates consent check → hash → retry-with-backoff `(2, 4, 8, 16s)` per KNOWLEDGE_BASE §10 → vault write → name match → append-only consent log
- [x] **P5.6** — `identity/vault.py` — HMAC-SHA256 hash (salt + NIN → hex digest) + Fernet ciphertext (32-byte key auto-derived from env)
- [x] **P5.7** — `consent_log` + `identity_records` tables; alembic `0004_identity_consent` verified on SQLite
- [x] **P5.8** — `identity/name_match.py` — `strict_match` + `fuzzy_match` tolerant of middle-name order, accents (NFKD + strip combining), 1-char typos, punctuation
- [x] **P5.9** — Mai tool: `verify_identity(nin, consent, declared_name, purpose)` — 12 tools total in the registry now
- [x] **P5.10** — Web: `/identity` page with language selector, 11-digit NIN input, declared-name field, explicit consent checkbox rendered in all 5 v1 languages, and a colour-coded result card (green verified / rose not-verified, with strict / fuzzy / mismatch name-match badge). Landing page links to it.
- [x] **P5.11** — End-to-end demo path documented in README: language → NIN → consent → Dojah → vault + consent-log → name match → continue to chat. Without Dojah creds the adapter still runs and surfaces a clean `aggregator_unavailable` reason.

## PHASE 6 — NRS Sandbox Handshake (Live Path Prep) ✅ SYNC PATH COMPLETE

- [x] **P6.1** — `gateway/signing.py` — HMAC-SHA256 signer + `hmac.compare_digest`-based `verify_signature`; rejects empty secrets.
- [x] **P6.2** — `gateway/timestamps.py` — ISO-20022 `iso_20022_now()`, `parse_iso_20022()`, and a 5-minute `within_replay_window` guard for inbound callbacks.
- [x] **P6.3** — `gateway/client.py` — `NRSClient` signs + posts, parses `NRSResponse` / `NRSRejection`, retries transport + 5xx with `(2, 4, 8, 16s)` backoff; missing credentials raise `NRSAuthError` for the service to catch and drop to simulation.
- [ ] **P6.4** — Celery setup + worker Docker service (**deferred** — awaiting Redis infra. The sync retry shape in `NRSClient` is intentionally a mirror of the eventual Celery task, so the move is a code-relocation, not a rewrite).
- [ ] **P6.5** — `submit_filing` task with backoff (deferred with P6.4).
- [x] **P6.6** — `Filing.nrs_irn`, `nrs_csid`, `nrs_qr_payload`, `submission_status`, `nrs_submission_error`, `nrs_submitted_at` via alembic `0005_filing_submission`. Migration chain `0001 → 0005` verified on SQLite.
- [x] **P6.7** — Sandbox smoke path — `POST /v1/filings/{id}/submit` exercised end-to-end against a mocked `HttpClient` (`tests/test_gateway_client.py` + `test_gateway_service.py` + `test_filings_endpoint.py`). With no NRS creds configured the service generates a deterministic `SIM-IRN-*` / `SIM-CSID-*` / `mai-filer://sim/...` receipt so the full UI loop still renders.
- [x] **P6.8** — `gateway/errors.py` — 8-code catalogue (AUTH, SIGNATURE, REPLAY, NIN-NOT-FOUND, PAYLOAD, COMPUTATION, RATE-LIMIT, UPSTREAM-DOWN) with per-code severity (`retryable` / `user_fix` / `fatal`) and per-language messages; English is the fallback.
- [x] **P6.9** — Mai Filer tool `submit_to_nrs(filing_id, language)` — 13 tools total in the registry.

## PHASE 7 — Rev360 Live + Accreditation

- [ ] **P7.1** — Engage an Access Point Provider (DigiTax / UsawaConnect) per ADR-0002 pre-APP path
- [ ] **P7.2** — NRS Developer Portal onboarding
- [ ] **P7.3** — Production credentials via Vault / KMS
- [ ] **P7.4** — Swap HMAC for JWT if NRS mandates post-Rev360
- [ ] **P7.5** — Observability: Prometheus + Grafana SLAs
- [ ] **P7.6** — NDPC DPCA audit workflow
- [ ] **P7.7** — NITDA code-clearance package

## PHASE 8 — Learning Partner

- [ ] **P8.1** — pgvector install + migration
- [ ] **P8.2** — `memory/facts.py` — structured yearly facts
- [ ] **P8.3** — `memory/recall.py` — semantic recall over prior filings
- [ ] **P8.4** — YoY anomaly detector (PIT variance, salary jumps)
- [ ] **P8.5** — Mid-year nudges

## PHASE 9 — SME (CIT / VAT / MBS) — **v2**

Guarded by ADR-0002. The post-deployment expansion track. Execution begins
when the owner supplies the regulatory data listed below.

### Data the owner must supply before production

The calculators + validators ship with **placeholder statutory tables**
so tests and local dev can run. They are loudly marked as
non-authoritative via `*_SOURCE = "PLACEHOLDER:..."` constants; every
tool response echoes this back in `statutory_is_placeholder: true`.
Endpoints moving to production call `assert_confirmed()` and refuse to
run until these drop in:

- 2026 CIT bands by turnover tier → `apps/api/app/tax/statutory/cit_bands.py`.
- 2026 WHT rates per transaction class → `apps/api/app/tax/statutory/wht_rates.py`.
- NRS UBL 3.0 **55 mandatory fields** list across 8 sections → `apps/api/app/tax/statutory/ubl_fields.py`.
- NRS criteria for "medium/large" taxpayer (decides who the 24-hour MBS sync applies to).
- Preferred Access Point Provider partner (DigiTax / UsawaConnect / …).

### Implementation tasks

- [x] **P9.0** — `tax/statutory/` package with placeholder CIT bands, WHT rates, and a 55-field-count-preserving UBL structure. Each table ships with a `_SOURCE` string that an `assert_confirmed()` guard can gate production on.
- [x] **P9.1** — `tax/cit.py` — `calculate_cit_2026()` dispatches on injectable bands + tertiary rate; returns tier, CIT amount, tertiary amount, total payable, and notes; 8 tests.
- [x] **P9.2** — `tax/wht.py` — `calculate_wht()` against injectable rate table; unknown class raises; 7 tests.
- [x] **P9.3** — `filing/ubl/` package — `UBLEnvelope` Pydantic + JSON + XML serializers + validator asserting 8-section / 55-field invariants and emitting structured findings; 8 tests.
- [ ] **P9.4** — MBS 24h sync Celery pipeline + backoff (deferred with P6.4/P6.5; the sync gateway path is already the shape of the eventual task).
- [ ] **P9.5** — E-invoice composer UI with QR + CSID rendering.
- [ ] **P9.6** — CAC verification flow (reuses Phase 5 aggregator adapters — same `IdentityAggregator` Protocol).
- [ ] **P9.7** — SME filing pack (UBL 3.0 JSON + branded PDF variant reusing Phase 4 renderer).
- [x] **P9.8** — Mai Filer tools: `calc_cit`, `calc_wht`, `list_wht_classes`, `validate_ubl_envelope`. Registry is now 17 tools. `compose_einvoice` and `submit_mbs` land with P9.5 / P9.4.
- [ ] **P9.9** — Landing + chat UI: "I'm filing for a business" entry path.

## PHASE 11 — NGO / Tax-Exempt Bodies — **v2+**

Not on the current roadmap until the owner supplies:

- NRS tax treatment for registered NGOs (income-tax exemption criteria,
  WHT remittance obligations on payments made by NGOs).
- NGO-specific return forms / cycles (annual report, WHT schedule, etc.).
- CAC part-C registration handling (distinct from regular CAC RC).

### Implementation tasks (post-data)

- [ ] **P11.1** — NGO taxpayer schema (CAC Part-C, exemption reference)
- [ ] **P11.2** — WHT remittance schedule calculator
- [ ] **P11.3** — Annual NGO return pack (PDF + JSON)
- [ ] **P11.4** — Audit Shield NGO-specific checks (proper exemption status,
      WHT collected matches remitted, etc.)
- [ ] **P11.5** — UI path "I am filing for an NGO"

## PHASE 10 — Polish

- [ ] **P10.1** — Dashboards (liability YTD, deadlines, deduction utilization)
- [ ] **P10.2** — Mobile-responsive polish
- [ ] **P10.3** — Accessibility audit (WCAG AA)
- [ ] **P10.4** — Additional Nigerian languages beyond v1 (e.g., Fulfulde) — subject to a later ADR

---

## Decisions Pending (Owner Input Required to Unblock)

These do **not** block v1 since v1 is individual-focused:

| Task(s) | Question |
|---|---|
| P2.12 | Exact 2026 CIT bands by turnover (v2) |
| P2.13 | Exact 2026 WHT rates per transaction class (v2) |
| P4.9 / P9.3 | Final list of NRS 55 mandatory fields across 8 sections (v2) |
| P9.x | Target license tier: PSP v1 → SI v2, or straight to APP? |
