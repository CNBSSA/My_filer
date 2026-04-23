# NITDA Software Clearance — Submission Package Template

> **Use**: skeleton for the NITDA code-clearance submission required
> for software handling government revenue data. Fill in the blanks,
> attach the evidence files listed under each section, and submit
> through the National Information Technology Development Agency
> clearance portal.

---

## 1. Entity information

| Field | Value |
|---|---|
| Company legal name | |
| CAC RC number | |
| Registered address | |
| Product name | **Mai Filer** |
| Product website | |
| Primary contact — Technical | |
| Primary contact — Legal / Compliance | |
| DPO (as registered with NDPC) | |

---

## 2. Product summary

Mai Filer is an AI-native Nigerian tax e-filing platform. It:

- Profiles individual taxpayers (PAYE / PIT, 2026 bands).
- Ingests payslips, bank statements, and receipts via Claude Vision
  with forced-tool structured output.
- Verifies NIN via a NIMC-licensed aggregator (default: Dojah).
- Computes 2026 PIT, PAYE, VAT, WHT, CIT, and Development Levy.
- Generates NRS-ready filing packs (JSON + branded PDF) after an
  automated Audit Shield review.
- Submits signed (HMAC-SHA256) filings to the NRS Rev360 endpoint.
- Maintains a year-over-year Learning Partner with anomaly detection
  and mid-year nudges.

All taxpayer conversation surfaces are multilingual: English, Hausa,
Yorùbá, Igbo, and Nigerian Pidgin.

---

## 3. Architecture summary

Attach `docs/ARCHITECTURE.md` (repo root) and
`docs/PRODUCTION_AWS.md §2` diagrams. Key facts to highlight:

- Monorepo: FastAPI backend (`apps/api/`) + Next.js frontend
  (`apps/web/`).
- Persistence: PostgreSQL 16 (ACID), Alembic-managed schema.
- Object storage: S3-compatible (behind `StorageAdapter` Protocol —
  swappable to Nigerian-hosted S3 per §5 below).
- Agent orchestrator: Claude (Opus 4.7 for Mai, Sonnet 4.6 for tools,
  Haiku 4.5 for cheap tasks) with prompt caching on the locked system
  prompt.
- Gateway: signed HMAC-SHA256 POST to NRS per `KNOWLEDGE_BASE.md §9`;
  JWT ready via `NRS_AUTH_SCHEME=jwt` if NRS mandates post-Rev360.

---

## 4. Indigenous content statement

Fill in honestly — NITDA weights indigenous engineering.

- Development team composition (Nigerian nationals %): ____
- Infrastructure vendors used:
  - Claude / Anthropic — foreign (no Nigerian equivalent for the
    reasoning model tier).
  - Dojah (Nigerian) — identity aggregator.
  - Galaxy Backbone / MainOne / Rack Centre (Nigerian) — primary
    host per the residency strategy.
  - AWS `af-south-1` (foreign, if Option A or C per
    `docs/PRODUCTION_AWS.md §1`).
- Open-source dependencies: listed in §7 SBOM below.

---

## 5. Data residency attestation

Mai Filer complies with NITDA data-residency guidelines by hosting
primary taxpayer and biometric data **inside Nigeria**. The current
implementation strategy is: `[Option A | Option B | Option C]` —
reference: `docs/PRODUCTION_AWS.md §1`.

Evidence to attach:

- Hosting contract with the Nigerian infrastructure partner.
- Network topology showing that the `RDS`-equivalent and object-storage
  servers have Nigerian IP prefixes.
- Cross-border data flow inventory (§6).

---

## 6. Cross-border data flow inventory

| Flow | Data | Destination | Lawful basis |
|---|---|---|---|
| Claude Vision document extraction | Uploaded document bytes | Anthropic (US / EU) | User consent; minimized PII |
| Dojah NIN lookup | NIN + consent flag | Dojah (Nigerian processor — no cross-border) | Consent; NIMC-licensed processor |
| NRS filing submission | Canonical pack | NRS (Nigerian) | NTAA statutory obligation |
| Web analytics / error reporting | Request metadata only | **TBD — none enabled in v1** | N/A |

---

## 7. Software Bill of Materials (SBOM)

### Backend (`apps/api/pyproject.toml`)

- `fastapi` — HTTP framework
- `uvicorn[standard]` — ASGI server
- `pydantic` / `pydantic-settings` — typed settings + validation
- `sqlalchemy` — ORM
- `psycopg[binary]` — Postgres driver
- `alembic` — schema migrations
- `celery[redis]` (deferred runtime)
- `anthropic` — Claude API SDK
- `httpx` — NRS + aggregator HTTP client
- `cryptography` — Fernet vault
- `python-multipart` — file uploads
- `python-dotenv` — dev env loading
- `orjson` — fast JSON
- `reportlab` — PDF rendering
- `PyJWT` — JWT signer (Phase 7)

### Frontend (`apps/web/package.json`)

- `next@16`
- `react@19`, `react-dom@19`
- `typescript@5`
- `tailwindcss@4`
- `eslint@9`, `eslint-config-next@16`

### Generating a full SBOM on release

```
# Python
pip install cyclonedx-bom
cd apps/api && cyclonedx-py -o ../../build/api-sbom.cdx.json

# Node
cd apps/web && npx @cyclonedx/cyclonedx-npm --output-file ../../build/web-sbom.cdx.json
```

Attach both files to the NITDA submission.

---

## 8. Security controls

| Control | Evidence file |
|---|---|
| Secrets management via AWS Secrets Manager (or Nigerian KMS partner) — no secrets in code | `app/secrets/`, `docs/PRODUCTION_AWS.md §3.3` |
| All HTTP traffic over TLS 1.2+ | ALB + ACM; WAF in front |
| NIN never stored in plaintext | `app/identity/vault.py`; `identity_records.nin_ciphertext` column |
| Consent gate on all NIN queries | `app/identity/service.py::verify_taxpayer` |
| Append-only consent log | `consent_log` table; no UPDATE/DELETE paths |
| Request signing for NRS traffic | `app/gateway/signing.py` (HMAC-SHA256) and `app/gateway/jwt_signing.py` (JWT) |
| Structured logging with correlation IDs | `app/observability/` |
| Principle of least privilege on IAM | Policy in `docs/PRODUCTION_AWS.md §4` |
| Automated dependency vulnerability scanning | CI workflow (e.g. `pip-audit` + `npm audit`) |
| Separate dev / staging / prod environments + secrets | `docs/PRODUCTION_AWS.md §5` |

---

## 9. No-backdoor statement

Mai Filer contains no covert access path, no undocumented administrative
endpoint, and no telemetry back-channel. The full production HTTP
surface is published in `docs/ARCHITECTURE.md` and is a union of the
routes declared in:

- `apps/api/app/api/chat.py`
- `apps/api/app/api/documents.py`
- `apps/api/app/api/filings.py`
- `apps/api/app/api/identity.py`
- `apps/api/app/api/memory.py`
- `apps/api/app/main.py::/health` and `/metrics`

Any route present in the code but not in that list is a defect.

NITDA auditors are welcome to run:

```
grep -rn '@router\.\(get\|post\|put\|delete\)' apps/api/app/api/
```

and compare with the published list.

---

## 10. Testing + quality posture

At the time of submission the test suite is **N tests** passing,
covering:

- Tax math: PIT bands, PAYE, CIT (via injectable bands), WHT, VAT, Dev Levy.
- Audit Shield: all 11 v1 checks.
- Filing pack: canonical JSON + PDF + validator.
- Gateway: signing, timestamps, client retry, error translation, service.
- Identity: vault (hash + encrypt), aggregator adapters, name match,
  service with retry.
- Memory: facts, recall, anomalies, nudges, auto-capture.
- Document ingestion: payslip / bank statement / receipt extractors.
- Mai Filer tool use: every tool exercised through the registry.
- HTTP endpoints: each router has an end-to-end test.

Build gates: `pytest` (Python), `tsc --noEmit` (TS), `next build`.

---

## 11. Submission checklist

- [ ] §1 Entity info filled
- [ ] §2 Product summary signed off by product lead
- [ ] §3 Architecture diagram exports attached
- [ ] §4 Indigenous content statement signed
- [ ] §5 Residency attestation + hosting contract attached
- [ ] §6 Cross-border data flow inventory accurate
- [ ] §7 SBOM (Python + Node) generated and attached
- [ ] §8 Security controls evidence attached
- [ ] §9 No-backdoor statement signed
- [ ] §10 Test report + CI URL attached
- [ ] Company legal authorisation letter
- [ ] Proof of CAC registration + TIN

Authorised signatory:

- Name: ______________________
- Title: _____________________
- Date: ______________________
- Signature: _________________
