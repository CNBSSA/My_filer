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
- [`docs/ROADMAP.md`](./docs/ROADMAP.md) — phased, smallest-task breakdown

## Repo layout

```
apps/api/        FastAPI backend + Claude orchestration + tax services
apps/web/        Next.js 15 + TS + Tailwind chat-first UI
packages/shared/ Shared TS types (mirrors Pydantic)
infra/           Docker, Alembic, operational scripts
docs/            Locked project documents (read these first)
```

## Local dev (once Phase 0 lands)

```bash
cp .env.example .env
docker compose up -d            # postgres + redis
cd apps/api && uv sync           # or: pip install -e .
uvicorn app.main:app --reload    # http://localhost:8000
```

## Branch policy

All development on `claude/mai-filer-bot-aQHn0` per project instructions.
