# Mai Filer — Master Plan (LOCKED ONCE APPROVED)

> One page. The contract between the owner and any AI assistant building this
> platform. No changes without express written approval.

---

## Vision

Build **Mai Filer**, an **AI-native Nigerian tax e-filing platform** peer to
TurboTax and TaxSlayer, born in the age of AI. Mai Filer is the agent **and**
the product: conversation drives filing. Short-term users file inside the app
and download NRS-compliant packs for manual submission; long-term Mai Filer
submits live to the NRS via Rev360.

## Locked Commitments

1. **Ten BIG Roles** (see `ROLES.md`). Non-shrinking.
2. **Stack** (see `CLAUDE.md §3`). Non-swappable without approval.
3. **Compliance Guardrails** (see `COMPLIANCE.md`). Non-negotiable.
4. **Knowledge Base** (see `KNOWLEDGE_BASE.md`) is the only source for rates,
   thresholds, and endpoints. No guessing.
5. **Smallest-task discipline** (see `ROADMAP.md`). Every change is a small,
   testable increment that ends in a commit.

## Phases (high-level)

| # | Phase | Outcome |
|---|---|---|
| 0 | Foundation | Monorepo + locked docs + dev env boots |
| 1 | Mai Filer Core | Chat with in-role Mai Filer (no tools yet) |
| 2 | Tax Calculators | PIT / VAT / PAYE / Dev Levy (CIT/WHT pending inputs) |
| 3 | Document Intelligence | Upload payslip → Mai extracts |
| 4 | Filing Pack Generator | Download UBL 3.0 / 55-field pack |
| 5 | NIN / CAC Verification | Verified users via aggregator |
| 6 | NRS Sandbox Handshake | Signed request reaches sandbox |
| 7 | Rev360 Live + Licensing | Real submissions, real license |
| 8 | Learning Partner | YoY memory + anomaly detection |
| 9 | Receipt & E-Invoice Co-Pilot | SME MBS co-pilot |
| 10 | Polish & Localization | Dashboards + Hausa/Yoruba/Igbo |

## Change Control

- Any deviation from this plan — scope, stack, roles, compliance, or
  ordering — requires a new approval message from the owner.
- "Small" changes inside an approved phase are allowed, but must still be
  reflected in `ROADMAP.md`.
- AI assistants must cite CLAUDE.md / the Knowledge Base when answering
  factual questions about Nigerian tax; never invent rates or endpoints.

## Definition of Done (per phase)

A phase is done only when all of:

- [ ] Every task in that phase in `ROADMAP.md` is checked off.
- [ ] Tests for that phase pass (`pytest` in `apps/api`, `vitest`/`playwright`
      in `apps/web` when applicable).
- [ ] Relevant docs updated.
- [ ] Commits pushed to `claude/mai-filer-bot-aQHn0`.
- [ ] A short demo path in the chat UI proves the phase works end-to-end.

## Signatures

- **Owner approval (to be captured in the conversation)**: _pending_
- **Locked date**: _on approval_
