# Mai Filer

An AI-native Nigerian tax e-filing platform. Mai Filer is the agent **and** the
product — conversation drives filing.

**Start here** → [`CLAUDE.md`](./CLAUDE.md)

## Docs

- [`docs/MASTER_PLAN.md`](./docs/MASTER_PLAN.md) — the locked one-page contract
- [`docs/KNOWLEDGE_BASE.md`](./docs/KNOWLEDGE_BASE.md) — 2026 Nigerian tax facts
- [`docs/ROLES.md`](./docs/ROLES.md) — the ten BIG roles of Mai Filer
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — system layout
- [`docs/COMPLIANCE.md`](./docs/COMPLIANCE.md) — NDPR, NITDA, NTAA, UBL 3.0
- [`docs/DECISIONS.md`](./docs/DECISIONS.md) — ADRs (plan, v1 scope, Dojah, multilingual)
- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — phased, smallest-task breakdown

## Repo layout

```
apps/api/        FastAPI backend + Claude orchestration + tax services
apps/web/        Next.js 16 + TS + Tailwind chat-first UI
packages/shared/ Shared TS types (mirrors Pydantic)
infra/           Docker, Alembic, operational scripts
docs/            Locked project documents (read these first)
```

## Run the Phase 3 demo end-to-end

You need two terminals and a `ANTHROPIC_API_KEY` for the live Claude calls.

```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY, leave the SQLite URL below for quick dev
echo 'DATABASE_URL=sqlite:///./mai_filer.db' >> .env
```

**Terminal 1 — backend**

```bash
cd apps/api
pip install -e ".[dev]"               # or: uv sync
alembic upgrade head                  # runs migrations 0001 + 0002
uvicorn app.main:app --reload         # http://localhost:8000
```

**Terminal 2 — web**

```bash
cd apps/web
npm install
npm run dev                           # http://localhost:3000
```

Then in the browser:

1. Open <http://localhost:3000/chat>.
2. Pick a language from the header dropdown (English / Hausa / Yorùbá / Igbo / Pidgin).
3. Say "hi Mai" — she introduces herself in-role.
4. Drag a payslip (PDF or image) onto the page, **or** click the 📎 button and pick one.
5. The UI uploads to `POST /v1/documents`, Claude Sonnet 4.6 Vision extracts the
   payslip via a forced tool call, and the structured extraction is attached to
   the next chat turn ("I just uploaded… please read it and walk me through…").
6. Mai calls `read_document_extraction`, then `calc_paye` on the extracted
   figures, then explains the 2026 PAYE band-by-band in your chosen language.

### Filing pack (Phase 4)

Once you have a complete return (NIN + name + at least one income source +
declaration affirmed), you can generate a downloadable pack:

- `POST /v1/filings` with a PITReturn body to create a filing.
- Mai Filer calls `audit_filing` (tool), then `prepare_filing_pack`, then
  surfaces the download URLs.
- Visit `http://localhost:3000/filings/<filing-id>` to review the Audit
  Shield report (green / yellow / red with itemized findings) and download
  the branded PDF or canonical JSON pack.

## Branch policy

All development on `claude/mai-filer-bot-aQHn0` per project instructions.
