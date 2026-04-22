# Mai Filer — Railway Deployment

> **Scope v1 (live on Railway)**: individual Nigerian taxpayers filing
> PIT / PAYE for the 2026 year. Companies (CIT / VAT / MBS e-invoicing)
> and NGOs are **not** included in this deployment — see ADR-0002 in
> `docs/DECISIONS.md` and the "Expanding coverage" section below.
>
> **Data residency reminder** (per `docs/COMPLIANCE.md §4`): production
> taxpayer data must sit inside Nigeria. Before accepting real NINs /
> filings, move the Postgres + object storage onto Galaxy Backbone or
> Rack Centre. Railway's default regions are outside Nigeria; using
> them for real taxpayer data is a NITDA violation.

---

## 1. Services on Railway

Two services, one Postgres plugin.

| Service | Root directory | Public |
|---|---|---|
| `mai-filer-api` | `apps/api` | yes (HTTPS) |
| `mai-filer-web` | `apps/web` | yes (HTTPS) |
| `postgres` (plugin) | — | private-link only |

Both services are Nixpacks builds (`railway.json` in each service root).
The web service talks to the API service over the public HTTPS URL.

## 2. First-time setup on Railway

1. In Railway, create a new project from the GitHub repo `cnbssa/my_filer`,
   tracking the `main` branch.
2. Add two services from the same repo:
   - **API**: Root directory = `apps/api`.
   - **Web**: Root directory = `apps/web`.
3. Add the **Postgres** plugin to the project. Railway injects
   `DATABASE_URL` automatically into every service that requests it.
   - On the API service, add a reference variable:
     `DATABASE_URL = ${{Postgres.DATABASE_URL}}` — then append
     `?sslmode=require` if Railway's connection string needs it.
   - Our SQLAlchemy URL is `postgresql+psycopg://...` flavour; if Railway
     gives you `postgres://` or `postgresql://`, Railway's built-in
     integration generally works because SA can negotiate — but for
     safety the API service env can explicitly set
     `DATABASE_URL=postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}`.
4. Set the required environment variables (next section).
5. Deploy — Railway will build both services on the first push to `main`.

## 3. Required environment variables

### API service (`apps/api`)

| Variable | Value | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | *your key* | Required. Mai Filer + Vision extractor both call Claude. |
| `CLAUDE_MODEL_ORCHESTRATOR` | `claude-opus-4-7` | Default is fine. |
| `CLAUDE_MODEL_TOOLS` | `claude-sonnet-4-6` | Used for payslip Vision extraction. |
| `CLAUDE_MODEL_CHEAP` | `claude-haiku-4-5-20251001` | Classification / summarization. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | See §2 above. |
| `CORS_ALLOW_ORIGINS` | `https://<web-service>.up.railway.app` | Comma-separated. Include the Railway-issued web URL after first deploy. |
| `APP_ENV` | `production` | Turns off debug affordances. |
| `NIN_HASH_SALT` | *32+ char random* | Salt for NIN hashing (Phase 5). |
| `NIN_VAULT_KEY` | *base64 32-byte* | Encryption key for the NIN ciphertext vault (Phase 5). |
| `JWT_SECRET` | *strong random* | Rotate on any suspected exposure. |
| `STORAGE_*` | (defaults OK for v1 ephemeral) | Pre-production; swap to Nigerian S3 before real users. |

### Web service (`apps/web`)

| Variable | Value | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://<api-service>.up.railway.app` | Copy after the API service's first deploy. |
| `NODE_ENV` | `production` | Enables Next.js production mode. |

## 4. Release flow

Every push to `main` triggers both services to rebuild. The API service's
`preDeployCommand` runs `alembic upgrade head` so schema changes apply
before any request is served. The new web build is swapped in only after
the API is healthy (`/health` returns 200).

If `alembic upgrade head` fails, Railway keeps the previous release live
and surfaces the error in the deploy log. Fix the migration on a new
branch, open a PR to `main`, and redeploy.

## 5. Health + monitoring

- API: `GET /health` returns `{ status: "ok", service, env, version }`.
- Web: `GET /` renders the landing page as a health proxy.

Connect Railway's healthcheck to `/health` on the API; the `railway.json`
already declares it. The web service uses `/` (dynamic renders still
succeed without the API if the DB is briefly down; the chat surfaces a
⚠️ badge until the API recovers).

## 6. Common problems

1. **Web can't reach API** — `NEXT_PUBLIC_API_BASE` wasn't updated after
   the API's first deploy, or `CORS_ALLOW_ORIGINS` on the API doesn't
   include the web URL. Update both, redeploy only the service you
   changed.
2. **Alembic fails on first deploy** — check `DATABASE_URL` is exported
   on the API service. If Railway gave you `postgres://...`, upgrade
   the driver prefix as in §2.
3. **CORS preflight fails** — confirm `CORS_ALLOW_ORIGINS` is a CSV
   of exact origins (protocol + host, no trailing slash).
4. **Long payload upload fails** — `POST /v1/documents` enforces a
   10 MB ceiling; Railway proxies add another implicit cap. If users
   hit this, document the limit rather than raising blindly — we keep
   small limits on NDPR-sensitive uploads by design.

## 7. Expanding coverage (companies + NGOs)

The Railway deployment ships the **individual** flow only. To expand:

1. Obtain the 2026 CIT bands (turnover tier → rate), WHT rates per
   transaction class, and the MBS 55-field UBL 3.0 field list. Add them
   to `docs/KNOWLEDGE_BASE.md` and reference the new ADRs.
2. Build Phase 9 (`apps/api/app/tax/cit.py`, `apps/api/app/tax/wht.py`,
   `apps/api/app/filing/ubl/…`, SME invoice composer).
3. Add an NGO-flavoured return schema reflecting NRS exemption + WHT
   reporting requirements.
4. Re-run Audit Shield with new checks; extend `/filings/[id]` UI.
5. No infra changes required — both services redeploy on push.

Until then, the Railway deployment is explicitly scoped to individuals
and the web landing + chat surface state this to users.
