# Mai Filer — Roadmap (Smallest-Task Breakdown)

> Every task below is sized so it can be executed, tested, and committed on
> its own. Each task has an ID (`P{phase}.{n}`) so the user can reference any
> one step ("do P2.3 next"). Statuses: `[ ]` pending · `[~]` in progress ·
> `[x]` done · `[!]` blocked.

---

## PHASE 0 — Foundation

Goal: clean monorepo, CLAUDE.md memory anchor, docs locked, dev env boots.

- [x] **P0.1** — Write `CLAUDE.md` memory anchor
- [x] **P0.2** — Write `docs/KNOWLEDGE_BASE.md`
- [x] **P0.3** — Write `docs/ROLES.md`
- [x] **P0.4** — Write `docs/ARCHITECTURE.md`
- [x] **P0.5** — Write `docs/COMPLIANCE.md`
- [~] **P0.6** — Write `docs/ROADMAP.md` (this file)
- [ ] **P0.7** — Write `docs/MASTER_PLAN.md` (one-page lock contract)
- [ ] **P0.8** — Create monorepo folders (`apps/api`, `apps/web`, `packages/shared`, `infra/`)
- [ ] **P0.9** — Add root `.gitignore` (Python + Node + secrets + OS)
- [ ] **P0.10** — Add root `.env.example` with every expected key
- [ ] **P0.11** — Add root `README.md` (brief — points to CLAUDE.md)
- [ ] **P0.12** — Create `apps/api/pyproject.toml` (FastAPI, Anthropic SDK, Pydantic, Ruff, pytest)
- [ ] **P0.13** — Create `apps/api/app/__init__.py` and `apps/api/app/main.py` with `/health`
- [ ] **P0.14** — Create `apps/api/app/config.py` with typed settings
- [ ] **P0.15** — Create `apps/api/tests/test_health.py`
- [ ] **P0.16** — Scaffold `apps/web` (Next.js 15 + TS + Tailwind)
- [ ] **P0.17** — Add `docker-compose.yml` (Postgres 16, Redis 7)
- [ ] **P0.18** — First commit + push to `claude/mai-filer-bot-aQHn0`

## PHASE 1 — Mai Filer Core (Agent Skeleton)

Goal: a live chat with Mai Filer that introduces herself in-role, with no
tools yet.

- [ ] **P1.1** — Install `anthropic` SDK in `apps/api`
- [ ] **P1.2** — Create `apps/api/app/agents/mai_filer/prompt.py` (v1 system prompt citing all 10 roles + Nigerian 2026 tax context)
- [ ] **P1.3** — Create `apps/api/app/agents/mai_filer/orchestrator.py` (Claude client wrapper, prompt caching on system block)
- [ ] **P1.4** — Add `/v1/chat` POST endpoint (non-streaming first)
- [ ] **P1.5** — Pydantic schemas: `ChatTurn`, `ChatRequest`, `ChatResponse`
- [ ] **P1.6** — Unit test the chat endpoint with a mocked Anthropic client
- [ ] **P1.7** — Add streaming variant at `/v1/chat/stream` (SSE)
- [ ] **P1.8** — DB: Alembic init; `threads`, `messages` tables
- [ ] **P1.9** — Persist every turn to Postgres
- [ ] **P1.10** — Web: `/chat` page with message list + input
- [ ] **P1.11** — Web: wire SSE stream to the UI
- [ ] **P1.12** — Web: thread list sidebar, load-by-id
- [ ] **P1.13** — Smoke test: "Hello Mai" → in-role introduction

## PHASE 2 — Tax Calculator Service (Pure Math)

Goal: every tax computation is a tested pure function; Mai can call them.

- [ ] **P2.1** — `apps/api/app/tax/pit.py` — `calculate_pit_2026(annual_income: Decimal) -> PITResult` with per-band breakdown
- [ ] **P2.2** — Unit tests for PIT covering each band boundary + zero + negative guard
- [ ] **P2.3** — `apps/api/app/tax/vat.py` — `calculate_vat(taxable_supply, exempt, rate=Decimal("0.075"))`
- [ ] **P2.4** — VAT threshold check: `is_vat_registrable(annual_turnover)` (₦100m)
- [ ] **P2.5** — VAT unit tests
- [ ] **P2.6** — `apps/api/app/tax/cit.py` — CIT per turnover tier (**blocked pending user input on 2026 bands**)
- [ ] **P2.7** — `apps/api/app/tax/wht.py` — WHT by class (**blocked pending user input on 2026 rates**)
- [ ] **P2.8** — `apps/api/app/tax/paye.py` — PAYE after CRA, pension, NHIS
- [ ] **P2.9** — PAYE unit tests
- [ ] **P2.10** — `apps/api/app/tax/dev_levy.py` — 4% Development Levy calculator
- [ ] **P2.11** — Register each calculator as a Claude tool (tool schemas in `agents/mai_filer/tools.py`)
- [ ] **P2.12** — Tool-use smoke test: "I earn ₦5m. What's my PIT?" → Mai calls `calculate_pit_2026` and explains bands
- [ ] **P2.13** — Optimizer pass: Mai proposes pension top-up / reliefs to reduce liability

## PHASE 3 — Document Intelligence

Goal: upload a payslip; Mai extracts structured data and pre-fills PAYE.

- [ ] **P3.1** — `POST /v1/documents` multipart endpoint
- [ ] **P3.2** — Storage adapter interface (`StorageAdapter`) + local MinIO dev impl
- [ ] **P3.3** — `documents/extractor.py` — Claude Sonnet 4.6 Vision call with structured-output schema
- [ ] **P3.4** — Payslip schema: gross, tax, pension, NHIS, CRA, period
- [ ] **P3.5** — Payslip extraction test with a sample fixture
- [ ] **P3.6** — Receipt schema + extractor
- [ ] **P3.7** — Bank statement schema + extractor
- [ ] **P3.8** — CAC certificate schema + extractor
- [ ] **P3.9** — Tool registration: `extract_document(file_id)` for Mai
- [ ] **P3.10** — Web: upload widget in chat; drag-and-drop
- [ ] **P3.11** — End-to-end: upload payslip → Mai acknowledges → PAYE pre-filled

## PHASE 4 — Filing Pack Generator (Short-Term Download Path)

Goal: user can download an NRS-compliant pack for manual submission.

- [ ] **P4.1** — `filing/schema.py` — Pydantic models for the 55 fields across 8 sections (**blocked pending user-provided field list**)
- [ ] **P4.2** — UBL 3.0 JSON serializer
- [ ] **P4.3** — UBL 3.0 XML serializer (`lxml`)
- [ ] **P4.4** — PDF renderer (`weasyprint` or `reportlab`)
- [ ] **P4.5** — Placeholder QR generator (replaced by CSID on live path)
- [ ] **P4.6** — `POST /v1/filings/{id}/pack` returns a signed download URL
- [ ] **P4.7** — Audit Shield validator: 55-field completeness + UBL schema pass
- [ ] **P4.8** — Audit Shield returns green / yellow / red with specifics
- [ ] **P4.9** — Mai runs Audit Shield before offering a download link
- [ ] **P4.10** — Web: "Review & download" flow with the shield report

## PHASE 5 — NIN / CAC Verification (via Aggregator)

Goal: verified identity before filing; consent captured.

- [ ] **P5.1** — `identity/base.py` — `IdentityAggregator` abstract base
- [ ] **P5.2** — `identity/dojah.py` adapter (default)
- [ ] **P5.3** — `identity/seamfix.py` adapter
- [ ] **P5.4** — `identity/prembly.py` adapter
- [ ] **P5.5** — `identity/service.py` — `verify_taxpayer(nin, consent)` with retry + backoff for NIN-TIN sync delay
- [ ] **P5.6** — NIN hashing util (salted SHA-256) + encrypted-vault writer
- [ ] **P5.7** — Consent model + append-only log table
- [ ] **P5.8** — Name-match utility (NIN record vs. return)
- [ ] **P5.9** — Tool registration: `verify_identity(nin)` for Mai
- [ ] **P5.10** — Web: NIN capture UI with explicit consent checkbox
- [ ] **P5.11** — End-to-end: user enters NIN, Mai verifies, proceeds

## PHASE 6 — NRS Sandbox Handshake (Live Path v1)

Goal: a signed request reaches NRS sandbox and returns a valid response shape.

- [ ] **P6.1** — `gateway/signing.py` — HMAC-SHA256 signer with unit tests
- [ ] **P6.2** — Timestamp utility (ISO-20022) + replay window guard
- [ ] **P6.3** — `gateway/nrs_client.py` — request envelope (headers + body)
- [ ] **P6.4** — Celery setup (`infra/celery.py`, worker Docker service)
- [ ] **P6.5** — `submit_filing` Celery task with exponential backoff (2,4,8,16s)
- [ ] **P6.6** — Store `IRN`, `CSID`, `QR` on success
- [ ] **P6.7** — Sandbox smoke test against a mock NRS endpoint
- [ ] **P6.8** — Rejection-reason translator: NRS error codes → plain-English Mai message

## PHASE 7 — Rev360 Live + Accreditation

Goal: real submissions, real license.

- [ ] **P7.1** — Engage an Access Point Provider (DigiTax / UsawaConnect) — partnership track
- [ ] **P7.2** — NRS Developer Portal onboarding (Client ID, Secret, Business ID)
- [ ] **P7.3** — Production credentials via Vault / KMS
- [ ] **P7.4** — Swap HMAC for JWT if NRS mandates post-Rev360
- [ ] **P7.5** — Observability: Prometheus + Grafana dashboards for submission SLAs
- [ ] **P7.6** — NDPC DPCA audit workflow
- [ ] **P7.7** — NITDA code-clearance package

## PHASE 8 — Learning Partner & Year-over-Year Memory

- [ ] **P8.1** — pgvector install + migration
- [ ] **P8.2** — `memory/facts.py` — structured yearly facts
- [ ] **P8.3** — `memory/recall.py` — semantic recall over prior filings
- [ ] **P8.4** — Anomaly detector (YoY VAT / PIT shifts)
- [ ] **P8.5** — Mid-year nudges ("you're trending toward VAT registration")

## PHASE 9 — Receipt & E-Invoice Co-Pilot (SME)

- [ ] **P9.1** — Invoice composer UI
- [ ] **P9.2** — 55-field invoice schema reuse from `filing/`
- [ ] **P9.3** — MBS submission within 24h via Celery
- [ ] **P9.4** — QR + CSID rendering on the final invoice

## PHASE 10 — Polish & Localization

- [ ] **P10.1** — Dashboards (liability YTD, deadlines, deduction utilization)
- [ ] **P10.2** — Multilingual: Hausa, Yoruba, Igbo explanation variants
- [ ] **P10.3** — Mobile-responsive chat
- [ ] **P10.4** — Accessibility audit (WCAG AA)

---

## Decisions Still Pending (Owner Must Answer Before the Task Unblocks)

| Task | Question |
|---|---|
| P2.6 | Exact 2026 CIT bands by turnover |
| P2.7 | Exact 2026 WHT rates per transaction class |
| P4.1 | Final list of the 55 NRS fields (8 sections) |
| P5.2–P5.4 | Chosen default aggregator (Dojah / Seamfix / Prembly) |
| P10.2 | Which Nigerian languages ship in v1 vs. later |
| — | Target license tier: PSP now, SI later? |
| — | First taxpayer type focus: individual (PAYE/PIT), SME (CIT/VAT), or parallel? |
