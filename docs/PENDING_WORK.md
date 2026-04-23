# Pending Work — Mai Filer Memory Anchor

> **Purpose**: a single durable reference for every piece of work that is
> not yet shipped. Any AI assistant (or human) resuming the project must
> read this file to avoid re-scaffolding things that already exist and to
> see exactly what the owner must supply to unblock each pending item.
>
> **Rule**: keep this file in sync with `ROADMAP.md`. When a pending item
> lands, move it out of "Pending" and into the phase section of
> `ROADMAP.md`, and update this doc.

---

## 1. Phase 7 — Rev360 Live + Accreditation

### Already shipped (post-Phase 7 opening commit)

See `docs/PRODUCTION_AWS.md`, `docs/NDPC_AUDIT_TEMPLATE.md`,
`docs/NITDA_CLEARANCE_TEMPLATE.md`, and the `app/secrets/`,
`app/gateway/jwt_signing.py`, `app/observability/` modules for the code +
doc scaffolding that landed before any owner action was required.

### What the owner must do (not code work)

| # | Task | Blocks |
|---|---|---|
| P7.1 | Engage an **Access Point Provider** (DigiTax / UsawaConnect / other) — sign MOU, obtain their sandbox submission URL | Real NRS submission; P9.4 MBS |
| P7.2 | **NRS Developer Portal** onboarding: register the business, obtain `Client ID`, `Client Secret`, `Business ID`, confirm the sandbox and production base URLs + endpoint paths | Phase 6 live path; P7.3 |
| P7.6 | **NDPC** registration as a *Data Controller of Major Importance*; engage a licensed DPCO for the annual DPCA audit | Handling real taxpayer data; P7 done |
| P7.7 | **NITDA** software clearance submission (package documented in `docs/NITDA_CLEARANCE_TEMPLATE.md`) | Government revenue software production readiness |
| P7.4 | Confirm **NRS post-Rev360 auth scheme** — HMAC-SHA256 today, possibly JWT after cutover. The code supports both via `NRS_AUTH_SCHEME=hmac|jwt`; the owner must tell us which to switch to and when | — |

---

## 2. AWS requirements of the owner

Full architecture + rationale in `docs/PRODUCTION_AWS.md`.
Hard-copy of the checklist lives there. This section is the short form.

### Account & identity
- [ ] AWS account created; root user has MFA hardware / TOTP enabled.
- [ ] Billing alerts configured (≥ $100 threshold minimum).
- [ ] IAM deploy-bot user / role with the scoped policy from
      `docs/PRODUCTION_AWS.md §4`.

### Region strategy (owner picks one)
- [ ] **Option A — staging only in `af-south-1` (Cape Town)**. Non-NITDA
      compliant; synthetic data only; fine for previews.
- [ ] **Option B — AWS Outposts inside a Nigerian data centre**
      (Galaxy Backbone / MainOne / Rack Centre). NITDA compliant.
      Long procurement cycle; high cost.
- [ ] **Option C — Hybrid**: Nigerian-hosted Postgres + object storage
      for PII; AWS `af-south-1` for non-PII services (frontend, cache,
      metrics). VPN or Direct Connect between.

### Services to provision (once region strategy is picked)
- [ ] VPC + public/private subnets + NAT gateway
- [ ] ALB with WAF in front
- [ ] ECS Fargate cluster (web + api services)
- [ ] RDS PostgreSQL 16 (multi-AZ for prod, single-AZ for staging)
- [ ] S3 bucket for uploads + filing packs, bucket policy locked to app role
- [ ] Secrets Manager (every NRS / Dojah / Anthropic secret lands here)
- [ ] CloudWatch Logs + Metrics + Alarms
- [ ] ACM cert for the production hostname
- [ ] ECR registry for api + web Docker images
- [ ] (Later) ElastiCache Redis for Celery when P6.4/P6.5 unblock

### Env vars Mai Filer reads from Secrets Manager (prod)
- `ANTHROPIC_API_KEY`
- `DATABASE_URL`
- `NRS_CLIENT_ID`, `NRS_CLIENT_SECRET`, `NRS_BUSINESS_ID`
- `DOJAH_API_KEY`, `DOJAH_APP_ID`
- `NIN_HASH_SALT`, `NIN_VAULT_KEY`
- `JWT_SECRET`

The application reads them via the `SecretsProvider` abstraction
(`app/secrets/`); set `SECRETS_BACKEND=aws` + `SECRETS_PATH_PREFIX=/mai-filer/prod/`
and the app picks them up without code changes.

---

## 3. Phase 9 — SME / CIT / VAT / MBS

### What's already live (no need to rebuild)

Quarantined scaffolding per ADR-0005. Replacing the three data files is
the full unlock path.

| Shipped | Where | State |
|---|---|---|
| `CITBand` dataclass + injectable calculator | `apps/api/app/tax/cit.py` | Logic done; `calculate_cit_2026()` injectable |
| WHT calculator | `apps/api/app/tax/wht.py` | Logic done; injectable `rates` map |
| UBL 3.0 envelope schema + validator (8 sections / 55 fields invariant) | `apps/api/app/filing/ubl/` | Invariants enforced |
| Placeholder statutory tables | `apps/api/app/tax/statutory/cit_bands.py`, `wht_rates.py`, `ubl_fields.py` | Loudly marked `SOURCE="PLACEHOLDER:..."` |
| `assert_confirmed()` guard | `apps/api/app/tax/statutory/__init__.py` | Refuses production if any placeholder source remains |
| Mai tools | `calc_cit`, `calc_wht`, `list_wht_classes`, `validate_ubl_envelope` | 17-tool registry includes these; every response echoes `statutory_is_placeholder: true` |

### Data the owner must supply

| Drop into | Content |
|---|---|
| `apps/api/app/tax/statutory/cit_bands.py` | 2026 CIT tiers (turnover cutoffs + rates), 2026 tertiary / education tax rate (or remove if the reform consolidated it), and replace `CIT_SOURCE` away from `"PLACEHOLDER:..."` |
| `apps/api/app/tax/statutory/wht_rates.py` | 2026 WHT rate per transaction class. Add new classes if NRS created any. Replace `WHT_SOURCE` |
| `apps/api/app/tax/statutory/ubl_fields.py` | Canonical UBL 3.0 paths for all 55 fields across the 8 fixed sections (keep the invariant — validator asserts it). Replace `UBL_SOURCE` |
| Business process | Choose an Access Point Provider partner and get their **MBS submission URL** — this goes into `Settings.nrs_base_url` / path for SME flow |

### Post-data Phase 9 work that unlocks

| Task | What's involved |
|---|---|
| P9.4 | MBS 24-hour sync Celery pipeline (depends on Redis infra — see §5 below). Existing `NRSClient` retry shape is the target task signature |
| P9.5 | E-invoice composer UI with QR + CSID rendering (reuses the existing web stack) |
| P9.6 | CAC verification adapter (reuses `identity.IdentityAggregator` Protocol — drop a new adapter beside `dojah.py`) |
| P9.7 | SME filing pack: UBL 3.0 JSON + branded PDF (reuses the Phase 4 renderer scaffold) |
| P9.9 | "I'm filing for a business" web entry path + new landing variant |

---

## 4. Phase 11 — NGO / Tax-Exempt

Backend scaffold is live (see `ROADMAP.md` Phase 11 for the file-path
inventory). Quarantined placeholders behind the same `_SOURCE` guard
pattern as Phase 9; flip to real rules by editing
`apps/api/app/tax/statutory/ngo_rules.py`.

### Data the owner must supply

- NRS-recognised exempt-purpose list → `NGO_EXEMPT_PURPOSES`.
- CAC Part-C RC number format → `NGO_CAC_PART_C_PATTERN`.
- NGO-specific WHT rates (if distinct from the general schedule) →
  `NGO_WHT_REMITTANCE`.
- Annual filing window / cycle → `NGO_FILING_WINDOW_MONTHS`.
- NRS NGO return form template (to drive a dedicated PDF renderer
  instead of the v1 shim over `filing/pdf.py`).

### Remaining work (unblocks immediately after web UI design choice)

- P11.5 — `/ngo` intake page with multilingual consent + review/download
  flow (mirrors `/identity` and `/filings/[id]`).

---

## 5. Deferred infrastructure work

| Deferred task | What it is | Unblocks when |
|---|---|---|
| **P6.4 / P6.5** | Celery worker + async submission task for NRS + MBS | Redis infra is provisioned (ElastiCache Redis is already on the AWS checklist) |
| **P8.10** | Portable embeddings + `VectorRecall` shipped; pgvector upgrade (direct `vector` column + ANN index on Postgres) | Postgres provisioned + volume justifies pgvector. Swap is a follow-up migration; the adapter layer does not change. |
| **Celery dashboards** | Flower / Grafana panels for job throughput | Ships with Celery |
| **Full UBL canonical XML signing** | xmldsig + C14N for signed UBL envelopes | NRS publishes the definitive XML schema + signing profile |

---

## 6. Cross-cutting compliance work

| Item | Owner action | Code state |
|---|---|---|
| NDPR / NDPC registration | Register as Data Controller of Major Importance; engage licensed DPCO | Consent log + audit trail plumbing is live (P5.7 + COMPLIANCE.md §6) |
| Annual DPCA audit | Run annually; template in `docs/NDPC_AUDIT_TEMPLATE.md` | — |
| NITDA software clearance | Submit per template | Package template in `docs/NITDA_CLEARANCE_TEMPLATE.md` |
| Data residency | Pick region strategy (see §2) | `SecretsProvider` + `StorageAdapter` already swappable |

---

## 7. How to update this file

1. When a pending item lands, delete its row here and tick the equivalent
   task in `ROADMAP.md`.
2. When a new blocker appears, add it to the correct section with a link
   to the commit that introduced the dependency.
3. When new owner-action items emerge (new regulatory change, new vendor
   onboarding), add them to section 1, 2, or 6 depending on type.
4. Run `grep -n PLACEHOLDER apps/api/app/` before shipping to prod — any
   hit is a `SOURCE` that needs a real value first.
