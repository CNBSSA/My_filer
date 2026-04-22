# Compliance Guardrails — Mai Filer

> Every item below is **non-negotiable** unless the user expressly waives it
> in the conversation. These are the rails the product rides on; crossing
> them is a defect, not a trade-off.

---

## 1. NDPR / NDPC (Data Protection)

- Register as a **Data Controller of Major Importance**.
- Annual **Data Protection Compliance Audit (DPCA)** by a licensed DPCO.
- **Consent** captured before every NIN query, every document upload, every
  NRS submission. Consent records are append-only and auditable.
- **Purpose limitation** — every access to taxpayer data logs its stated
  purpose.
- **Right to erasure** — honored except where NRS retention law overrides.
- **Raw NIN never stored** in the primary database. Persist only:
  - a salted SHA-256 hash (for lookup), and
  - a ciphertext in an encrypted vault, keyed per environment.

## 2. NITDA (Software Clearance)

- Submit to NITDA code audit before production launch.
- No backdoors, no hidden data exfiltration, no telemetry outside Nigeria.
- Favor indigenous open-source dependencies where equivalent.
- Secrets must not be committed to the repository — enforced via pre-commit
  hook.

## 3. NTAA 2026 (Tax Administration)

- Medium/large taxpayer invoices synced to MBS within **24 hours**.
- NIN (individuals) and CAC RC (businesses) are the **only** valid primary
  identifiers.
- Filing packs must conform to **UBL 3.0** and include all **55 mandatory
  fields** across 8 sections.
- Cryptographic stamp (IRN + CSID + QR) from NRS must be rendered on every
  accepted invoice.

## 4. Data Residency

- Primary tax and biometric data resides on **servers inside Nigeria**.
  Prod targets: **Galaxy Backbone** or **Rack Centre**.
- Cross-border transit allowed only for transient processing and only under
  NDPC data transfer provisions.
- LLM calls to Anthropic are allowed; **no taxpayer PII in prompts** without
  minimization + redaction. NIN, bank account numbers, and CAC-linked
  identifiers are masked before leaving the environment.

## 5. Secrets & Keys

- `.env` in local dev, gitignored.
- **Vault** (HashiCorp / cloud KMS) in production.
- NRS Client Secret, aggregator API keys, vault master keys are **never**
  logged, never shipped in client bundles, never in commit diffs.
- Keys rotate on a schedule and on every suspected exposure.

## 6. Audit Trail (append-only)

Every one of these events is logged with actor, timestamp, purpose,
correlation ID, and consent reference:

- NIN / CAC verification call
- Document upload
- Tax calculation
- Filing pack generation
- NRS submission attempt
- NRS response (success / rejection)
- Data access by operator (support)
- Data export / download by user

Logs are write-once for the retention window required by NTAA.

## 7. Pre-Submission Checklist (Audit Shield)

Before any filing pack leaves Mai Filer, the Audit Shield verifies:

- [ ] All 55 fields present and non-null where required.
- [ ] UBL 3.0 schema validation passes.
- [ ] NIN matches the name on the return.
- [ ] Totals recomputed and match declared values.
- [ ] Consent record exists for every data source used.
- [ ] No PII leaks in the payload beyond what NRS mandates.
- [ ] Timestamp in ISO-20022 format.
- [ ] Signature header present (live path).

## 8. Forward Compatibility

- NRS may migrate HMAC-SHA256 → **JWT** after Rev360 cutover. The gateway
  must swap via interface, not a code rewrite.
- Identity aggregators may change pricing or be deprecated. One adapter per
  vendor; the rest of the system is vendor-agnostic.
- State portals (LIRS, ESIRS, AKSG, etc.) are out of v1 scope but must be
  reachable through the same filing-service abstraction when added.
