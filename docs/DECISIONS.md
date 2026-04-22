# Architecture Decision Records — Mai Filer

> Durable record of every significant decision, with the research that drove
> it. An ADR is append-only: superseding an ADR requires a new ADR that cites
> the one it replaces. All ADRs require owner approval in the conversation
> before they are locked.

---

## ADR-0001 — Master Plan Approved

- **Status**: Accepted (owner, 2026-04-22).
- **Context**: The master plan in `docs/MASTER_PLAN.md` was drafted from the
  owner's stated vision: an AI-native Nigerian tax e-filing platform peer to
  TurboTax / TaxSlayer, centered on the Mai Filer agent. Scope creep was
  explicitly flagged as a risk.
- **Decision**: The master plan, the ten BIG roles in `ROLES.md`, the stack in
  `CLAUDE.md §3`, and the compliance guardrails in `COMPLIANCE.md` are
  **locked**. Any change requires a new owner approval.
- **Consequences**: Future tasks cite the plan by its IDs (`P{phase}.{n}`).
  AI assistants must refuse to silently deviate; they must stop and ask.

---

## ADR-0002 — v1 Taxpayer Focus: Individual (PAYE / PIT)

- **Status**: Accepted (owner, 2026-04-22, delegated-decision).
- **Context**: We have to choose where to spend the first 4–8 weeks of build
  effort. Options: Individual (PAYE / PIT), SME (CIT / VAT / e-invoice), or
  parallel.
- **Research**
  - **Addressable market in formal filing** — Nigeria's largest *filing-ready*
    cohort is PAYE employees. SMEs outnumber PAYE workers in raw count, but the
    overwhelming majority are informal and out of v1's compliance perimeter.
  - **Product-comparable precedent** — TurboTax, TaxSlayer, and every major
    tax-software success launched with individuals first and added SMB later.
    The reverse order rarely works: SMB demands enterprise-grade trust before
    the first shipped line of code.
  - **Regulatory complexity** — PAYE is single-employer, single-return, with
    deductible categories (CRA, pension, NHIS) already well-understood. SME
    requires MBS 24-hour real-time sync, UBL 3.0 with 55 mandatory fields,
    CSID / IRN / QR cryptographic stamps, and (ultimately) an Access Point
    Provider partnership. That is an order of magnitude more surface area.
  - **Capability reuse** — Every Mai Filer role (document intelligence,
    calculator, audit shield, filing pack, explanation engine) built for
    individuals is *directly reusable* for SMEs. Going individual first loses
    nothing and de-risks the SME phase.
  - **Headline-risk asymmetry** — An individual filing error is personally
    painful; an SME error can trigger the 4% Development Levy penalty and kill
    a business. Building the muscle on the lower-stakes surface is the
    responsible path.
- **Decision**: **Individual (PAYE / PIT) is v1.** SME (CIT / VAT /
  e-invoicing / MBS) becomes v2 — Phase 9 in `ROADMAP.md` remains scoped, but
  execution waits until the individual path is live and polished.
- **Consequences**
  - Phase 2 tax math prioritizes `pit.py`, `paye.py`, and the Dev-Levy
    calculator last (only because it affects corporate filings).
  - Phase 3 Document Intelligence focuses on payslips first, receipts /
    bank statements / contracts second, CAC / MBS artifacts deferred.
  - Phase 4 Filing Pack Generator outputs an individual PAYE / PIT pack first;
    the UBL 3.0 55-field work is scaffolded but exercised on the SME phase.
  - Phase 5 Identity primarily uses NIN flow; CAC flow stubbed.
  - Phase 9 (SME) is time-boxed later and will be its own master-plan
    supplement when we reach it.

---

## ADR-0003 — Default Identity Aggregator: Dojah

- **Status**: Accepted (owner, 2026-04-22, delegated-decision).
- **Context**: Per `KNOWLEDGE_BASE.md §10`, three aggregators dominate
  NIMC-licensed identity verification in Nigeria: **Dojah, Seamfix, Prembly**.
  We need a default to ship v1 without blocking on a procurement cycle.
- **Research**
  - **Dojah** — API-first, modern REST surface, self-serve keys in minutes,
    wallet-based billing, transparent per-call pricing in the range cited by
    the owner (₦150–₦250 / verification). Service coverage spans NIN, BVN,
    CAC, phone, email, address — which supports both the individual path
    (v1, NIN) and the SME path (v2, CAC) without adding a vendor.
  - **Seamfix** — 20+ years in Nigerian identity; NIMC-accredited; highly
    respected; but its sales motion is enterprise, contract-heavy, and slow
    to onboard. Good second-source or fallback; not first choice for an
    AI-native build that iterates weekly.
  - **Prembly** — Strong developer experience, multi-country footprint
    (Nigeria, Kenya, Ghana), excellent compliance posture. Competitive on
    NIN/BVN. Close runner-up to Dojah; we keep it as the primary alternate.
  - **Architecture already abstracts the choice** — `identity/base.py`
    defines `IdentityAggregator`; Dojah / Seamfix / Prembly each become a
    thin adapter (`P5.2 / P5.3 / P5.4`). The cost of switching is one file,
    not a rewrite.
- **Decision**: **Dojah is the default aggregator for v1.** Seamfix and
  Prembly remain as implemented alternates behind the same interface. The
  `IDENTITY_AGGREGATOR=dojah` env flag is the single switch.
- **Consequences**
  - Phase 5 builds and exercises the Dojah adapter first (`P5.2`).
  - Dojah credentials live in `.env` (`DOJAH_API_KEY`, `DOJAH_APP_ID`).
  - Seamfix / Prembly adapters ship as code but are not wired into CI smoke
    tests until a concrete reason arises.
  - If Dojah pricing or reliability regresses, a later ADR can swap the
    default by changing a single env var.

---

## ADR-0004 — v1 is Multilingual

- **Status**: Accepted (owner, 2026-04-22, explicit).
- **Context**: The owner confirmed multilingual support is a v1 requirement,
  not a Phase-10 polish item. Nigeria is a multi-language country; taxpayers
  outside the English-dominant urban elite are a majority of the filing-ready
  population. The Explanation Engine role (Role 5) cannot do its job in
  English only.
- **Research**
  - **Languages to ship** — English (official, required for every NRS
    payload), **Hausa** (~80M speakers, dominant in the north), **Yoruba**
    (~50M, southwest), **Igbo** (~40M, southeast), and **Nigerian Pidgin**
    (the de-facto national lingua franca, understood across all regions).
  - **Where language applies**
    - Mai Filer conversational output → the taxpayer's chosen language.
    - UI chrome (buttons, labels, forms) → i18n'd via `next-intl`.
    - Tax jargon glossary → per-language entries.
    - Consent flows → **must** be in the user's chosen language per NDPR
      purpose-limitation requirements.
  - **Where language does NOT apply**
    - The filing payload to NRS is always English / machine-readable UBL 3.0.
    - Audit logs are always English.
    - The stored system prompt and tool schemas are English.
  - **LLM fit** — Claude Opus 4.7 / Sonnet 4.6 are strong on Yoruba, Igbo,
    and Hausa. Quality is good but not perfect, so we provide a
    per-language style guide and a QA flow that flags low-confidence
    translations back to an English fallback with a note.
  - **Roadmap impact** — The "multilingual" task previously in Phase 10 is
    promoted into the v1 loop. It splits across Phase 1 (language selector +
    system-prompt localization variants) and Phase 5 (consent-flow
    translations).
- **Decision**: **v1 ships with English + Hausa + Yoruba + Igbo + Pidgin.**
  Any added Nigerian language (e.g., Fulfulde, Tiv, Kanuri) is a later ADR.
- **Consequences**
  - Add a `language` column to the user / thread model.
  - Add `apps/api/app/i18n/` with per-language system-prompt addenda and
    jargon glossaries.
  - Add `apps/web/messages/{en,ha,yo,ig,pcm}.json` for UI strings.
  - The `/v1/chat` request carries a `language` preference; the orchestrator
    steers Claude output accordingly.
  - Phase 1 adds P1.14–P1.16 for i18n scaffolding; Phase 5 adds consent
    translations as part of P5.10.

---

## How to add a new ADR

1. Copy the block format above.
2. Cite the ADR you supersede (if any) in the **Status** line.
3. Include Context, Research, Decision, Consequences.
4. The owner must approve in the conversation before the ADR is Accepted.
5. Reflect consequences in `ROADMAP.md` tasks the same commit.
