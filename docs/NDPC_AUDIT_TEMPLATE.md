# NDPC Data Protection Compliance Audit — Template

> **Use**: Hand this template to the licensed DPCO before the annual
> DPCA. It maps Mai Filer's data-handling posture to the NDPR / NDPC
> requirements so the auditor can verify by inspecting the named files
> and endpoints.
>
> **Rule**: the technical facts here must match the code at audit time.
> When `app/identity/`, `app/memory/`, `app/gateway/`, or `app/documents/`
> change, update the affected section.

---

## 0. Registration status

- [ ] Mai Filer registered with NDPC as a **Data Controller of
      Major Importance** (DCMI) — date + registration reference:
- [ ] Licensed Data Protection Compliance Organisation (DPCO) engaged —
      name + licence number:
- [ ] Data Protection Officer (DPO) appointed — name + contact:

---

## 1. Data inventory

| Personal data field | Purpose | Source | Storage | Retention |
|---|---|---|---|---|
| NIN (raw) | NRS-mandated taxpayer identifier | User entry via `/identity` | **Never stored raw.** Fernet-encrypted ciphertext in `identity_records.nin_ciphertext`; key in Secrets Manager | Lifetime of taxpayer record or until user erasure request |
| NIN hash (HMAC-SHA256 salted) | Join key across `consent_log`, `identity_records`, `yearly_facts` | Derived | `VARCHAR(64)` column | Lifetime |
| Full name | NRS filing; name-match audit check | NIMC record via aggregator + user-declared | `identity_records.full_name` + filing return JSON | Lifetime of taxpayer record |
| Date of birth | NIMC record; identity correlation | Aggregator response | `identity_records.date_of_birth` | Lifetime |
| State of origin | NIMC record | Aggregator response | `identity_records.state_of_origin` | Lifetime |
| Phone number | NIMC record | Aggregator response | `identity_records.phone` (if present) | Lifetime |
| Email | Filing contact | User entry | `filings.return_json.taxpayer.email` | NTAA retention window |
| Address | Filing contact | User entry | `filings.return_json.taxpayer.residential_address` | NTAA retention window |
| Payslip / receipt / bank statement content | Document intelligence feeds calculators | User upload | Object storage (S3 or Nigerian host) keyed by `documents.storage_key`; **extracted** structured data in `documents.extraction_json` | NTAA retention window |
| Filing numerical facts | Learning Partner / anomaly detection | Auto-capture on submission | `yearly_facts.value` (stringified Decimal) | NTAA retention window |
| NRS submission receipt (IRN / CSID / QR) | Proof of filing | NRS response | `filings.nrs_*` columns | NTAA retention window |

**PII boundary enforcement**:
- NIN never appears in logs (verified by `grep -n 'nin' apps/api/app/`
  — only hashed or ciphertext references).
- Bank account numbers stored as **last-4 only** (`documents/schemas.py`
  `BankStatementExtraction.account_number_last4` max length = 4).
- Anthropic prompts avoid PII where possible (payslip extraction is an
  exception — it's the user's own document and the user has consented).

---

## 2. Lawful basis

- **Consent** (NDPR s. 2.2(a)) for every identity verification and
  document upload.
- **Compliance with a legal obligation** (NDPR s. 2.2(c)) for
  NTAA-mandated submission of tax returns.
- **Contract performance** for the filing-pack generation the user
  explicitly requests.

Evidence locations:
- `app/identity/service.py` — refuses any NIN lookup without
  `consent=True`; raises `ConsentRequiredError` otherwise.
- `app/api/identity.py` — HTTP 400 on `consent=false`.
- `consent_log` table — append-only row per NIN query recording the
  consent flag, purpose, outcome, timestamp.
- `docs/COMPLIANCE.md §6` — the full audit-log contract.

---

## 3. Consent records

### 3.1 Capture

- UI: `/identity` page presents the consent body in the user's chosen
  language (`apps/web/messages/{en,ha,yo,ig,pcm}.json` → `identity.consentBody`).
- Submit button is disabled until the checkbox is ticked **and** the
  NIN passes format validation.
- API: `POST /v1/identity/verify` refuses `consent:false`.

### 3.2 Storage

- `consent_log` row per query: `user_id`, `thread_id`, `nin_hash`,
  `aggregator`, `purpose`, `consent_granted`, `outcome`,
  `name_match_status`, `error_message`, `created_at`.
- Append-only — no UPDATE / DELETE paths in the code.

### 3.3 Evidence for audit

```sql
SELECT count(*)
     , consent_granted
     , outcome
FROM   consent_log
WHERE  created_at >= NOW() - INTERVAL '1 year'
GROUP BY consent_granted, outcome;
```

Expect: `consent_granted = false` count = 0. Any row with
`consent_granted = false` is a defect.

---

## 4. Retention schedule

| Data class | Retention | Rationale |
|---|---|---|
| NIN ciphertext + hash | Lifetime of user account, then crypto-erased (key rotation invalidates all ciphertexts) | NTAA requires identifier persistence; NDPR allows erasure on request |
| Filing `return_json` + NRS receipt | NTAA statutory retention (confirm exact window with the DPCO) | Tax records retention mandate |
| Uploaded documents | 7 years after the tax year they support (NRS convention; confirm with DPCO) | Matches NTAA audit window |
| `consent_log` | 10 years minimum | Demonstrable compliance history |
| `yearly_facts` | Lifetime of user account | Learning Partner recall |
| Chat transcripts | 2 years (tunable) | Service improvement + user history |

**Implementation status**: retention tasks are **not automated yet**.
For v1, purges happen on request via a manual ops runbook. Automated
retention jobs land in a post-launch hardening task.

---

## 5. Right to erasure

- NDPR grants data subjects the right to request deletion.
- Mai Filer's obligation is limited by NTAA (tax records must survive
  the statutory window).

Process (documented for the DPO):

1. User submits erasure request via the DPO email of record.
2. DPO verifies identity (out-of-band).
3. Engineering runs the erasure job (manual for v1):
   - Clear `identity_records.nin_ciphertext` (keep the hash for join
     integrity on non-PII facts).
   - Null out `taxpayer.email`, `taxpayer.residential_address`,
     `taxpayer.phone` on `filings.return_json`.
   - Delete `documents.storage_key` from object storage; keep the row
     with `kind='erased'`.
   - Do **not** delete `consent_log` (lawful basis for retention).
4. DPO confirms completion in writing within 30 days (NDPR requirement).

---

## 6. Data transfer posture

- **Claude API** (Anthropic): document content goes over HTTPS for
  Vision extraction. NIN / bank account numbers are minimised (last-4
  only for accounts). Anthropic is a processor, not a controller.
- **Identity aggregator** (Dojah default, per ADR-0003): NIN +
  `consent: true` flag over HTTPS. Aggregator is a sub-processor.
- **NRS**: signed HMAC-SHA256 payloads over HTTPS. NRS is the data
  controller for the portion of the record it ingests.
- **Storage**: per data-residency strategy (`docs/PRODUCTION_AWS.md §1`).

All transfer agreements should be attached to the DPCO's working file.

---

## 7. Breach protocol

1. **Detect** — CloudWatch alarm on error-rate spike OR manual discovery.
2. **Contain** — rotate all secrets (Secrets Manager + `NIN_VAULT_KEY`
   first). `app/secrets/` is the only touch point for secret rotation
   in code.
3. **Assess** — what data left the perimeter? Cross-reference
   `consent_log` + `cloudwatch` for the affected window.
4. **Notify** — NDPC within 72 hours if PII was compromised (NDPR s. 4).
5. **Notify data subjects** — without undue delay where the risk is
   high to rights and freedoms.
6. **Record** — append to an internal breach register with root cause
   + corrective action.

---

## 8. Annual DPCA checklist

The DPCO's audit should at minimum:

- [ ] Verify §1 inventory matches the schema.
- [ ] Sample `consent_log` for integrity (no `consent=false` rows).
- [ ] Confirm `identity_records.nin_ciphertext` decrypts only with the
      current `NIN_VAULT_KEY`; attempt with a rotated key — must fail.
- [ ] Confirm uploaded documents are gone from object storage for any
      filing marked `erased`.
- [ ] Verify TLS posture (HSTS, modern ciphers) on the public ALB.
- [ ] Verify IAM posture: least-privilege, MFA on root, no long-lived
      access keys outside the deploy bot.
- [ ] Confirm retention schedules (§4) are respected.
- [ ] Review breach register since last audit.

Sign-off:

- DPO: ______________________  Date: ______
- DPCO: ____________________  Date: ______
