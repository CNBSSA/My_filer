# Mai Filer — System Architecture

> Service-oriented, AI-native. The orchestrator prompt is a thin router; real
> work lives in typed services exposed as Claude tools. No business logic in
> prompts. No prompts embedded in business logic.

---

## 1. High-Level Diagram (ASCII)

```
          +--------------------------+
          |   Next.js 15 Web App     |   chat-first UI, dashboards, uploads
          |   (apps/web)             |
          +-----------+--------------+
                      | HTTPS (SSE for chat streaming)
                      v
          +--------------------------+
          |   FastAPI Gateway        |   auth, rate-limits, SSE, file upload
          |   (apps/api)             |
          +-----+------+------+------+
                |      |      |
                v      v      v
      +------------+ +------------+ +--------------------+
      |  Mai Filer | |  Tax       | |  Filing Gateway    |
      |  Agent     | |  Services  | |  (NRS / MBS)       |
      |  (Claude)  | |  (pure)    | |  (async Celery)    |
      +-----+------+ +------+-----+ +---------+----------+
            |               |                 |
            |               v                 v
            |        +---------------+  +-----------------+
            |        |   Postgres 16 |  |   Redis 7       |
            |        |   + pgvector  |  |   (Celery broker)
            |        +---------------+  +-----------------+
            v
   +------------------+
   |  Sub-agents via  |
   |  Claude tools:   |
   |  - Calculator    |
   |  - Doc Intel     |
   |  - Verifier      |
   |  - Audit Shield  |
   |  - Filer         |
   +------------------+
```

## 2. Monorepo Layout

```
My_filer/
├── CLAUDE.md                   # memory anchor (read first)
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml          # postgres + redis + (later) minio
├── docs/
│   ├── KNOWLEDGE_BASE.md
│   ├── MASTER_PLAN.md
│   ├── ROLES.md
│   ├── ARCHITECTURE.md         # this file
│   ├── COMPLIANCE.md
│   └── ROADMAP.md
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── pyproject.toml
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── agents/
│   │   │   │   └── mai_filer/
│   │   │   │       ├── prompt.py
│   │   │   │       ├── tools.py
│   │   │   │       └── orchestrator.py
│   │   │   ├── tax/            # pure calculators
│   │   │   │   ├── pit.py
│   │   │   │   ├── cit.py
│   │   │   │   ├── vat.py
│   │   │   │   ├── wht.py
│   │   │   │   ├── paye.py
│   │   │   │   └── dev_levy.py
│   │   │   ├── documents/      # ingest + extraction
│   │   │   ├── identity/       # NIN / CAC verification (aggregator adapters)
│   │   │   ├── filing/         # UBL 3.0 pack generation + PDF
│   │   │   ├── gateway/        # NRS handshake (HMAC / OAuth2)
│   │   │   ├── compliance/     # 55-field validators, threshold watchers
│   │   │   ├── memory/         # pgvector + structured user memory
│   │   │   ├── db/             # SQLAlchemy models, migrations (Alembic)
│   │   │   └── api/            # FastAPI routers
│   │   └── tests/
│   └── web/                    # Next.js 15 + TS + Tailwind
│       ├── package.json
│       ├── src/
│       │   ├── app/
│       │   │   ├── layout.tsx
│       │   │   ├── page.tsx        # landing
│       │   │   ├── chat/page.tsx   # Mai Filer chat
│       │   │   └── dashboard/
│       │   ├── components/
│       │   └── lib/
│       └── public/
├── packages/
│   └── shared/                 # shared TS types (mirrors Pydantic models)
└── infra/
    ├── alembic/                # DB migrations
    └── scripts/
```

## 3. Service Boundaries

Each service below is a Python package under `apps/api/app/` with a stable,
typed interface. The Mai Filer orchestrator only ever touches services through
their exported tool functions.

| Service | Responsibility | Primary Role Served |
|---|---|---|
| `tax/` | Pure tax math (PIT, CIT, VAT, WHT, PAYE, Dev Levy) | Role 3 |
| `documents/` | Upload, OCR, extraction via Claude Vision | Role 2 |
| `identity/` | NIN / CAC verification (aggregator-swappable) | Roles 1, 6 |
| `filing/` | UBL 3.0 + 55-field pack generation, PDF rendering | Role 7 |
| `gateway/` | NRS handshake: HMAC-SHA256 now, OAuth2 / JWT later | Role 7 |
| `compliance/` | Threshold watchers, 55-field validators, deadline clock | Roles 4, 6 |
| `memory/` | User profile, year-over-year facts, pgvector recall | Role 8 |
| `agents/mai_filer/` | Orchestrator prompt + tool registry | Role 1, 10 |

## 4. Data Flow — "User files their 2025 PAYE" (short-term path)

1. User opens `/chat` → WebSocket / SSE to FastAPI.
2. Mai Filer greets, asks intent ("File PAYE for 2025").
3. Mai requests the user's NIN → `identity.verify_taxpayer(nin, consent=True)`.
4. Mai asks for payslips → user uploads → `documents.extract_payslips(files)`.
5. Mai calls `tax.paye(...)` → returns computed liability + breakdown.
6. Mai explains each line (Role 5) and proposes reliefs (Role 3 optimizer).
7. User confirms → `filing.generate_pack(user, year="2025", type="PAYE")`
   returns UBL 3.0 JSON + XML + PDF.
8. Audit Shield (Role 6) validates the pack; returns green/yellow/red.
9. On green, user downloads the pack for manual submission at NRS portal.

## 5. Data Flow — live NRS submission (long-term path)

Replaces step 9 above:

9a. `gateway.submit(pack)` enqueues a Celery task.
9b. Worker signs with HMAC-SHA256 (or OAuth2 / JWT post-Rev360).
9c. NRS returns IRN + CSID + QR on success → persisted against the filing.
9d. Failure → exponential backoff (2s, 4s, 8s, 16s); after 4 tries → surface
   error to Mai; she explains the NRS rejection reason in plain English.

## 6. LLM Strategy

- **Opus 4.7** — Mai Filer orchestrator (reasoning, routing, user dialogue).
- **Sonnet 4.6** — Document Intelligence (Vision), Audit Shield (validation).
- **Haiku 4.5** — classification, intent detection, summarization.
- **Prompt caching** — mandatory on the system prompt + tax law context +
  user's prior filings. This is both a cost and latency optimization.
- **Structured output** — every tool uses a Pydantic schema; parsing failures
  are never silently swallowed.

## 7. Storage

- **Postgres 16** — all durable facts: users, filings, line items, audit logs.
- **pgvector** — chunked tax law, user conversation memory, prior filings for
  semantic recall.
- **Object storage** — S3-compatible, **Nigerian-hosted** (Rack Centre /
  Galaxy Backbone in prod; MinIO in local dev). Holds uploaded PDFs and
  generated filing packs.
- **Secrets** — `.env` in dev; Vault / cloud KMS in prod. Raw NIN never in
  Postgres — only its salted hash + a ciphertext in the encrypted vault.

## 8. Auth

- Users authenticate with NIN + one-time password (delivered via SMS / email).
- Session = short-lived JWT; refresh token rotated on use.
- Consent log is append-only and linked to every NIN query.

## 9. Observability

- Structured JSON logs with a correlation ID per chat turn.
- Every tool invocation logs: tool name, args hash, latency, cache hit/miss,
  token counts.
- Filing submissions log: attempt count, NRS response code, IRN (on success).
- NDPC-grade audit trail: every access to taxpayer data is recorded with
  actor, purpose, and consent reference.

## 10. Swappable Boundaries (design for change)

These must stay behind interfaces — the owner has flagged each as likely to
change:

- **Identity aggregator** (Dojah / Seamfix / Prembly) — one adapter per vendor.
- **NRS auth scheme** (HMAC-SHA256 → JWT post-Rev360) — one signer interface.
- **Object storage** (MinIO local → Nigerian S3 prod) — one storage adapter.
- **LLM provider** — although we commit to Claude, the agent module exposes a
  thin wrapper so tests can inject fakes.
