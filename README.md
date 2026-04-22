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
- [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) — Railway setup, env vars, release flow
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
alembic upgrade head                 # applies migrations 0001 → 0003
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
