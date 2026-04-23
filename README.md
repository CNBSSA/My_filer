# Mai Filer

An AI-native Nigerian tax e-filing platform. Mai Filer is the agent **and** the
product — conversation drives filing.

**Start here** → [`CLAUDE.md`](./CLAUDE.md)

## Current coverage

| Taxpayer class | Status |
|---|---|
| Individuals (PAYE / PIT 2026) | ✅ live — calc, audit, pack (PDF + JSON), review UI |
| Sole proprietors / freelancers | ✅ via the PIT path (income kind = `self_employment`) |
| Companies (CIT / VAT / MBS e-invoicing) | ❌ Phase 9 — blocked on 2026 CIT bands, WHT rates, and the 55-field UBL 3.0 list |
| NGOs / tax-exempt bodies | ❌ Phase 11 — needs owner input on NRS exemption + reporting |

### Document ingestion (Claude Vision, forced structured output)

| Kind | Status |
|---|---|
| Payslip | ✅ extracts gross, PAYE, pension, NHIS, CRA, net pay, other lines |
| Bank statement | ✅ per-transaction categorization (salary / rent / pension / NHIS / NHF / tax payment / …); account-number last-4 only |
| Receipt / invoice | ✅ typed by receipt_type (insurance / medical / utility / rent / donation / …), supports reliefs and expense substantiation |
| CAC certificate | ❌ scaffolded — schema lands with Phase 9 |

See `docs/DECISIONS.md` (ADR-0002) for the locked v1 scope and
`docs/DEPLOYMENT.md §7` for how to expand coverage.

## Docs

- [`docs/MASTER_PLAN.md`](./docs/MASTER_PLAN.md) — the locked one-page contract
- [`docs/KNOWLEDGE_BASE.md`](./docs/KNOWLEDGE_BASE.md) — 2026 Nigerian tax facts
- [`docs/ROLES.md`](./docs/ROLES.md) — the ten BIG roles of Mai Filer
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — system layout
- [`docs/COMPLIANCE.md`](./docs/COMPLIANCE.md) — NDPR, NITDA, NTAA, UBL 3.0
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — ADRs (plan, v1 scope, Dojah, multilingual)
- [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) — Railway setup, env vars, release flow (preview only)
- [`docs/PRODUCTION_AWS.md`](./docs/PRODUCTION_AWS.md) — AWS production architecture + owner checklist
- [`docs/NDPC_AUDIT_TEMPLATE.md`](./docs/NDPC_AUDIT_TEMPLATE.md) — DPCA audit workflow
- [`docs/NITDA_CLEARANCE_TEMPLATE.md`](./docs/NITDA_CLEARANCE_TEMPLATE.md) — NITDA clearance submission package
- [`docs/PENDING_WORK.md`](./docs/PENDING_WORK.md) — memory anchor for everything not yet shipped
- [`docs/ACCESSIBILITY.md`](./docs/ACCESSIBILITY.md) — WCAG 2.2 AA test harness + regression gate
- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — phased, smallest-task breakdown

## Repo layout

```
apps/api/        FastAPI backend + Claude orchestration + tax services + alembic
apps/web/        Next.js 16 + TS + Tailwind chat-first UI
packages/shared/ Shared TS types (mirrors Pydantic)
infra/           Shared dev infrastructure (docker-compose, scripts)
docs/            Locked project documents (read these first)
```

## Run locally

You need `ANTHROPIC_API_KEY` for the live Claude calls.

```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY; for quick local dev you can use SQLite:
echo 'DATABASE_URL=sqlite:///./mai_filer.db' >> .env
```

**Terminal 1 — backend**

```bash
cd apps/api
pip install -e ".[dev]"              # or: uv sync
alembic upgrade head                 # applies migrations 0001 → 0004
uvicorn app.main:app --reload        # http://localhost:8000
```

**Terminal 2 — web**

```bash
cd apps/web
npm install
npm run dev                          # http://localhost:3000
```

### End-to-end demo flow

1. Open <http://localhost:3000/chat>.
2. Pick a language (English / Hausa / Yorùbá / Igbo / Pidgin).
3. Say "hi Mai" — she introduces herself in-role.
4. Drag a payslip (PDF or image) onto the page, **or** click 📎 and pick one.
5. The UI posts to `POST /v1/documents`; Claude Sonnet 4.6 Vision extracts
   the structured data; Mai is auto-told about the new document.
6. Mai calls `read_document_extraction`, then `calc_paye`, then explains the
   2026 PAYE band-by-band in your language.
7. When you're ready, Mai creates a `Filing` via `POST /v1/filings`, runs
   the Audit Shield, and — if green — generates the NRS-ready pack.
8. Visit `http://localhost:3000/filings/<filing-id>` to review findings
   and download the branded PDF + canonical JSON.

### Identity verification (Phase 5)

Before any real filing, verify the NIN against the NIMC record via a
licensed aggregator (**Dojah** by default — ADR-0003).

- Visit <http://localhost:3000/identity>. Pick a language, type the
  11-digit NIN, optionally declare the name on the return, tick the
  consent checkbox, and submit.
- The UI posts to `POST /v1/identity/verify`, which:
  1. Rejects anything without `consent=true` (NDPR / NDPC).
  2. HMAC-hashes the NIN (salt = `NIN_HASH_SALT`) and calls Dojah.
  3. Retries transport failures with `2s → 4s → 8s → 16s` backoff for
     the NIN-TIN sync window (KNOWLEDGE_BASE §10); clean vendor
     rejections do NOT consume retries.
  4. On a valid record, Fernet-encrypts the raw NIN (key = `NIN_VAULT_KEY`)
     and upserts `identity_records`.
  5. Runs strict + fuzzy name-match against your declared name.
  6. Appends an immutable `consent_log` row regardless of outcome.
- From chat, Mai calls the same pipeline via her `verify_identity` tool
  — she refuses any NIN query without the user's explicit yes.

Local dev without Dojah credentials: the adapter still runs, you'll
just see `verified=false` with `aggregator_unavailable` as the reason.
Set `DOJAH_API_KEY` and `DOJAH_APP_ID` in `.env` to exercise the real
endpoint.

### NRS submission (Phase 6)

After Audit Shield is green (or yellow), Mai can submit the pack to
NRS via the signed HMAC-SHA256 gateway.

- `POST /v1/filings/{id}/submit` — the backend rebuilds the canonical
  pack, signs with `HMAC_SHA256(payload + timestamp, NRS_CLIENT_SECRET)`,
  sets `X-API-Key` / `X-API-Business-Id` / `X-API-Timestamp` /
  `X-API-Signature` headers, POSTs to `$NRS_BASE_URL/efiling/pit/submit`.
  - 2xx → persists `IRN`, `CSID`, `qr_payload` on the `Filing` row and
    sets `submission_status=accepted`.
  - 4xx → `submission_status=rejected`; error is run through the
    translator and stored with the vendor raw message.
  - 5xx / network → retries `2s → 4s → 8s → 16s`; if still failing,
    `submission_status=error`.
- **Simulation mode** — when `NRS_CLIENT_ID` / `NRS_CLIENT_SECRET` /
  `NRS_BUSINESS_ID` aren't configured (local dev, Railway preview), the
  service generates a deterministic `SIM-IRN-*` / `SIM-CSID-*` /
  `mai-filer://sim/...` receipt and marks `submission_status=simulated`.
  The UI + Mai tool clearly label the preview so nobody mistakes it for
  a real NRS acceptance.
- From chat, Mai calls her `submit_to_nrs` tool, which returns the same
  payload (including `simulated: true` when applicable) so she can
  communicate the status in the user's language.
- Celery-backed async submission (`P6.4/P6.5`) is deferred until the
  Redis infra is in place; the sync retry shape matches the eventual
  task so the move is a code-relocation.

## Deploy on Railway

See [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) for the full setup. Short
version: two services (`apps/api` and `apps/web`) + the Postgres plugin,
each auto-detected by Nixpacks from its `railway.json`. Migrations run on
every release via `preDeployCommand`.

**Data residency note** — Railway's default regions are outside Nigeria.
Before accepting real taxpayer data, move Postgres + object storage to a
Nigerian host (Galaxy Backbone / Rack Centre). This is NITDA-mandatory,
not a nicety.

## Branch policy

- `main` — what Railway deploys.
- `claude/mai-filer-bot-aQHn0` — active feature branch. All new work pushes
  here first; PRs bring it into `main`.
