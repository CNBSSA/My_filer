# Mai Filer — The Ten BIG Roles (LOCKED)

> Mai Filer is not a helper. She is the platform. These ten roles define what
> she does; they do not shrink. Each role maps to a sub-agent or a tool in the
> agentic system. Approval locks this list — additions or removals require
> express user approval.

---

## Role 1 — Taxpayer Concierge (Orchestrator)

The face of the platform. Every user conversation starts here.

**Responsibilities**
- Profile the taxpayer: salaried (PAYE), self-employed, SME owner, landlord,
  multi-income, diaspora.
- Build a personalized filing plan and sequence.
- Delegate to sub-agents (roles 2–9) via Claude tool use.
- Maintain conversational continuity — greet, remember, close the loop.

**Model**: Claude Opus 4.7 (primary reasoning, tool orchestration).
**Tools**: all sub-agent tools below are registered on this orchestrator.

---

## Role 2 — Document Intelligence

Turns messy inputs into clean, structured tax data.

**Accepted inputs**
- Payslips (PDF / image) → gross, CRA, pension, NHIS, PAYE withheld.
- Bank statements → income discovery, deductible expense candidates.
- Receipts → VAT input tax, allowable deductions.
- Contracts → withholding tax exposure, service classification.
- CAC certificates → business ID, registration date, directors.
- Prior-year filings → carry-forward losses, consistency checks.

**Model**: Claude Sonnet 4.6 with Vision (cheaper than Opus; tolerates batch).
**Output**: Pydantic-typed structured data written into the user's tax
profile.

---

## Role 3 — Calculator & Optimizer

The math brain. Pure, deterministic, tested.

**Responsibilities**
- **PIT** using the 2026 bands (see `KNOWLEDGE_BASE.md` §3).
- **CIT** per turnover tier.
- **VAT** at 7.5% with the ₦100m registration threshold.
- **WHT** by transaction class.
- **PAYE** after CRA, pension, NHIS deductions.
- **Development Levy** (4%) where triggered.
- **Optimizer layer** — explore legal reliefs, pension top-ups, deductible
  categories to minimize liability.

**Implementation**: pure Python functions in `apps/api/app/tax/`, 100% unit
tested, wrapped as tools for Mai Filer.

---

## Role 4 — Compliance Advisor

Proactive, not reactive.

**Responsibilities**
- Track the 24-hour MBS sync window.
- Watch turnover against the ₦100m VAT threshold; warn before it's crossed.
- Enforce the 55-field rule on every outbound filing.
- Surface deadline reminders (NRS filing cycles, PAYE remittance dates).
- Flag scenarios that trigger the Development Levy.

---

## Role 5 — Explanation Engine

Mai Filer never lets the user submit something they don't understand.

**Responsibilities**
- Plain-language explanation of every line item, every form field, every
  number on screen.
- Show the math, not just the answer.
- Cite the rule ("this comes from NTAA 2026, s. X").
- **v1**: English only. **Roadmap**: Hausa, Yoruba, Igbo.

---

## Role 6 — Audit Shield

Pre-submission reviewer. Catches what NRS would catch — before NRS sees it.

**Responsibilities**
- Validate the 55-field payload against UBL 3.0 schema.
- Cross-check NIN name vs. return name.
- Recompute totals; compare to declared.
- Flag missing consent, missing attachments, mismatched TINs.
- Produce a "green / yellow / red" readiness report.

**Model**: Sonnet 4.6 (deterministic validation + short reasoning).

---

## Role 7 — Filing Orchestrator

The bridge to NRS.

**Short-term (no license yet)**
- Generate UBL 3.0 JSON + XML packs.
- Render a clean PDF for manual upload to the NRS Self-Service Portal.
- Render placeholder QR (replaced by real CSID on acceptance).

**Long-term (through Access Point Provider, then direct SI)**
- OAuth2 onboarding with NRS.
- HMAC-SHA256 signing (per `KNOWLEDGE_BASE.md` §9).
- Celery-backed async submission + retry on NRS downtime.
- Store IRN, CSID, QR on acceptance.

---

## Role 8 — Learning Partner

Turns the platform into a year-over-year advisor.

**Responsibilities**
- Persistent memory of prior filings, deductions, income sources.
- Anomaly detection: "your Q2 VAT collection is 40% below last year — worth a
  look."
- Suggest mid-year adjustments to avoid March-April surprises.
- Personal KPIs: effective tax rate, YoY delta, deduction utilization.

**Implementation**: pgvector for semantic recall + structured Postgres facts.

---

## Role 9 — Receipt & E-Invoice Co-Pilot

For SME users. Keeps them MBS-compliant in real time.

**Responsibilities**
- Compose MBS-compliant e-invoices with all 55 fields.
- Submit to NRS within the 24-hour window.
- Attach QR + CSID on return.
- Store invoice history for the Learning Partner.

---

## Role 10 — Multi-Agent Orchestrator (Architectural Role)

This is the **system property**, not a conversational face: Mai Filer (role 1)
does not compute, extract, or submit directly. She routes to specialized
sub-agents via Claude tool use. That separation is load-bearing — it keeps
each sub-agent testable, swappable, and auditable.

**Implication for every task going forward**
- No business logic runs inside the orchestrator prompt.
- Every capability ships as a tool with a Pydantic schema.
- The orchestrator chooses tools; the tools do work.
