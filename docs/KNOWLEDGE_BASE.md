# Knowledge Base — Nigerian Tax E-Filing 2026

> **Source of truth for all regulatory, technical, and market facts shared by
> the project owner.** Any AI assistant working on Mai Filer must treat this
> document as authoritative. Do not invent rates, thresholds, or endpoints.
> If a needed fact is not here, ask the user — do not guess.

---

## 1. Mission (as stated by the owner)

> "I am building a Nigerian tax e-filing system. The long-term goal is to
> connect to NRS; short-term is to file online and download the necessary packs
> for filing and submission with NRS. A very vital and big part is the Bot named
> **Mai Filer**, who helps users get the best out of filing taxes; making it easy
> with explanations along the way and maximizing tax benefits for the user."

> "Do not forget the big roles of the agentic named Mai Filer. It is a bigger
> platform like TurboTax, TaxSlayer, and the rest, born in the age of AI. It is
> an AI-native application."

## 2. Regulatory Shift (2026)

- **Nigeria Tax Reform Acts** took full effect **1 January 2026**.
- **FIRS → NRS**: the Federal Inland Revenue Service has become the **Nigeria
  Revenue Service (NRS)**.
- **TaxPro Max → Rev360**: Rev360 is the successor platform (official launch
  referenced as **30 April 2026**; medium-taxpayer go-live **1 July 2026**).
- Filing model shifted from periodic / batch to **mandatory real-time digital
  compliance**. End-of-month batching is **legally non-compliant** for medium
  and large taxpayers.
- All invoices must be validated by the NRS **within 24 hours** of the
  transaction via the **Merchant-Buyer Solution (MBS)**.

## 3. Personal Income Tax (PIT) Bands — 2026

Progressive, applied to **annual income**, computed in order:

| Band | Range | Rate |
|---|---|---|
| 1 | ₦0 – ₦800,000 | 0% (exempt) |
| 2 | Next ₦2,200,000 (₦800,001 – ₦3,000,000) | 15% |
| 3 | Next ₦9,000,000 (₦3,000,001 – ₦12,000,000) | 18% |
| 4 | Next ₦13,000,000 (₦12,000,001 – ₦25,000,000) | 21% |
| 5 | Next ₦25,000,000 (₦25,000,001 – ₦50,000,000) | 23% |
| 6 | Above ₦50,000,000 | up to 25% |

## 4. Other Tax Elements

- **VAT** — standard rate is **7.5%**. Registration / filing required once
  turnover exceeds **₦100,000,000 per annum** (the "₦100m threshold").
- **Development Levy** — **4%** on assessable profits for large corporations.
  Penalties apply if triggered but not collected.
- **CIT (Corporate Income Tax)** — tiered by turnover; application must encode
  small / medium / large thresholds.
- **WHT (Withholding Tax)** — varies by transaction class.
- **PAYE** — applied on employment income after consolidated relief allowance
  (CRA), pension, NHIS, and other statutory deductions.

## 5. Four Legal Frameworks (all must be complied with)

1. **Nigeria Tax Administration Act (NTAA) 2026** — gives NRS legal power to
   mandate real-time reporting; 24-hour sync rule.
2. **NITDA Act (software clearance)** — National Information Technology
   Development Agency must audit the software for backdoors and indigenous
   content; mandatory because this is government-revenue software.
3. **NDPR / NDPC** — Nigeria Data Protection Regulation / Commission; annual
   Data Protection Compliance Audit (DPCA) required; register as a Data
   Controller of Major Importance.
4. **Finance Act 2023/24 amendments** — **NIN** is the primary identifier for
   individuals; **CAC RC Number** for businesses. Legacy TINs are deprecated.

## 6. The Three-Tier E-Filing Landscape

| Tier | Type | Examples |
|---|---|---|
| **1 — Federal** | Core authority | NRS Self-Service Portal (successor to TaxPro Max); Merchant-Buyer Solution (MBS) |
| **2 — State** | Sub-national portals | LIRS eTax (Lagos), ESIRS (Enugu), AKSG e-Tax (Akwa Ibom) — each siloed |
| **3 — Private** | NRS-certified System Integrators | Pillarcraft (UsawaConnect), DigiTax (Namiri Technology), Heirs Technologies; fintechs such as Sparkle and Duplo |

Roughly **10–15 officially recognized private System Integrators** exist at the
federal level as of April 2026.

## 7. License Tiers (choose one operating model)

| License | Role | Barrier |
|---|---|---|
| **System Integrator (SI)** | Connects third-party software (ERPs) to NRS | High technical audit; ₦50m–₦100m professional indemnity insurance |
| **Access Point Provider (APP)** | Official gateway for data transmission | Strictest security clearance; direct MOU with NRS |
| **Private Service Provider (PSP)** | Niche e-filing app for specific sectors | Must connect **through** an accredited APP |

**Owner's chosen short-term path**: build as a **Private Service Provider**
that connects through an existing Access Point Provider (e.g., DigiTax /
UsawaConnect). Pursue SI / APP licensing as a later milestone. This avoids a
multi-million-naira legal and technical hurdle on day one.

## 8. Technical Standards (non-negotiable)

- **UBL 3.0** (Universal Business Language) — the XML / JSON interchange format
  for all e-invoices and filings sent to NRS.
- **The 55-Field Rule** — every e-invoice or filing payload must contain
  exactly **55 mandatory data fields** organized into **8 sections**
  (Seller info, Buyer info, Line items, Tax breakdown, etc.).
- **Cryptographic Stamp** — every accepted filing receives:
  - **IRN** (Invoice Reference Number)
  - **CSID** (Cryptographic Stamp Identifier)
  - **QR code** — must be rendered on every invoice
- **Data residency** — primary tax and biometric data must reside on servers
  **within Nigeria**. Local-region cloud (Galaxy Backbone, Rack Centre) or a
  compliant proxy is required.
- **Timestamp format** — ISO-20022.

## 9. NRS Secured Handshake (HMAC model)

Credentials issued by the NRS Developer Portal:

1. **Client ID** — `X-API-Key` header; public identifier.
2. **Client Secret** — used to sign requests; never logged or committed.
3. **Business ID** — the entity's ID within NRS.

Required per-request headers:

- `X-API-Key`  — the Client ID
- `X-API-Timestamp`  — ISO-20022 timestamp
- `X-API-Signature` — `HMAC_SHA256(payload + timestamp, client_secret)` hex digest
- `Content-Type: application/json`

Purpose: prevents tamper-in-flight (any digit changed → signature mismatch →
rejection) and replay attacks (timestamp window).

**Forward risk** — NRS may migrate from HMAC-SHA256 to **JWT** for high-volume
users after Rev360 cutover. Gateway code must be swappable.

**Sandbox endpoint (reference form)** — `https://api.nrs.gov.ng/v1/efiling/validate`

## 10. NIN / CAC Verification

Two paths; the chosen default is the second:

1. **Direct NIMC integration** — formal request to the DG of NIMC, NDA/MOU,
   setup fee, months of lead time.
2. **Certified aggregators** — **Dojah, Seamfix, Prembly**. API key in minutes.
   Cost per verification: **₦150–₦250**.

Mandatory per 2026 Data Protection laws: every NIN query **must** include an
explicit `consent: true` flag. Missing consent → NRS flags the app for a
privacy violation.

Workflow required:

1. **Verify** — confirm the NIN exists.
2. **Match** — compare NIN-on-record name with tax-return name (prevents
   identity fraud).
3. **Store securely** — hash + encrypted vault; raw NIN never persisted in
   the main database.

**Known timing quirk** — NIN-TIN sync delay of **24–72 hours** after a new
NIN is issued; verification must implement retry + backoff.

## 11. The Owner's Three-Step Execution Cycle

All new work on this project follows the owner's cycle:

1. **The Audit** — what's the regulatory / technical landscape and current
   state?
2. **Suggest Improvements** — propose clean, scalable architecture before
   writing code.
3. **Carry Out the Build** — code, tested, in small increments.

## 12. Reference Snippets Provided by the Owner

The following snippets were provided as direction. They are not final code;
they guide implementation in `apps/api/app/`. Final versions will live under
the service modules described in `ARCHITECTURE.md`.

- `calculator.py` — `calculate_pit_2026(annual_income)` applying the 6 bands.
- `security.py` — `generate_nrs_signature(secret_key, payload, timestamp)`
  returning an HMAC-SHA256 hex digest.
- `client.py` — `perform_handshake(tax_data)` sending the signed request to
  the NRS validate endpoint.
- `identity.py` — `IdentityService.verify_taxpayer(nin)` calling an aggregator
  with `consent: True` and returning the user profile for auto-fill.

## 13. Headline Risks to Design Against

- **April 30 cutover** — NRS may change auth scheme mid-build.
- **VAT threshold miscalculation** — a wrong ₦100m check exposes the client to
  the 4% Development Levy penalty.
- **Digital certificates in plain text** — NITDA audit failure; use `.env` or
  a key vault.
- **Non-local hosting** — using AWS us-east without a Nigerian proxy is an
  NITDA violation.
- **Missing consent flag** — NDPC violation, immediate flag.

## 14. What This Knowledge Base Does NOT Cover Yet (ask user before assuming)

- Exact CIT band thresholds for 2026 (small / medium / large turnover cutoffs).
- Exact WHT rates per transaction class for 2026.
- Final list of 55 fields and their 8 sections.
- NRS criteria for "medium / large" taxpayer triggering the 24-hour MBS sync.
- Preferred Access Point Provider partner (DigiTax / UsawaConnect / ...).
- State portal integration priority (which state portals, if any, for v1).

These will be resolved by direct owner answer, not by guessing.

### Where placeholders live in the code

Phase 9 ships calculators + envelope validators whose *math* is
production-ready, but the statutory *rates and field names* are still
pending owner confirmation. Placeholders are quarantined to a single
package so an owner-supplied update is a one-directory change:

- `apps/api/app/tax/statutory/cit_bands.py` — `CIT_BANDS_2026` + `CIT_TERTIARY_RATE` + `CIT_SOURCE`
- `apps/api/app/tax/statutory/wht_rates.py` — `WHT_RATES_2026` + `WHT_SOURCE`
- `apps/api/app/tax/statutory/ubl_fields.py` — `UBL_REQUIRED_FIELDS_2026` + `UBL_SECTIONS` + `UBL_SOURCE`

Each table ships with a `SOURCE` string that starts with `"PLACEHOLDER:"`
until the owner replaces it. Every Mai tool that touches these tables
echoes `statutory_is_placeholder: true` on its response so the agent can
caveat any figure it quotes. Endpoints bound for production call
`assert_confirmed()` on the relevant source string and refuse to run
while the placeholder marker is in place.
