import Link from "next/link";

export const metadata = {
  title: "How Mai Filer works",
  description:
    "Walk-through of how Mai Filer profiles you, reads your documents, computes your tax, runs an audit, and prepares an NRS-ready filing pack.",
};

interface Step {
  no: string;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    no: "1",
    title: "Talk to Mai, in your language",
    body:
      "Conversation drives the filing — not forms. Mai opens the chat in English, Hausa, Yorùbá, Igbo, or Naijá, asks who you are (PAYE / freelancer / SME / NGO), and builds a personalised filing plan from there.",
  },
  {
    no: "2",
    title: "Send your documents — payslip, receipts, statements",
    body:
      "Upload a photo or PDF of a payslip, bank statement, contract, or CAC certificate. Claude Vision reads them, extracts the structured numbers, and asks you to confirm anything ambiguous before it lands in your return.",
  },
  {
    no: "3",
    title: "She does the math — bands, reliefs, deductions",
    body:
      "Mai applies the 2026 PIT bands progressively (₦0 / 0%, then 15%, 18%, 21%, 23%, 25%), works in pension, NHIS, NHF, CRA, and other reliefs, and tells you exactly what each naira of liability comes from. CIT, VAT, PAYE, Development Levy and WHT are the same pure calculators.",
  },
  {
    no: "4",
    title: "Audit Shield runs every check before you submit",
    body:
      "11 structural checks for individuals, 10 for corporates, 11 for NGOs — NIN format, name match against NIMC, future tax years, declarations affirmed, schedule consistency, supporting docs. Findings come back as green, yellow, or red. You only download a pack if it's green or yellow.",
  },
  {
    no: "5",
    title: "Download a filing pack — PDF + canonical JSON",
    body:
      "A signed, time-stamped PDF you can read like a real return, plus a JSON pack with every line item. Today: print + manually submit at the NRS portal. Once NRS Rev360 sandbox credentials are wired, Mai submits directly and pulls back the IRN + CSID + QR code.",
  },
];

interface Role {
  no: string;
  name: string;
  body: string;
}

const ROLES: Role[] = [
  {
    no: "01",
    name: "Taxpayer Concierge",
    body: "Profiles you and builds the filing plan you actually need.",
  },
  {
    no: "02",
    name: "Document Intelligence",
    body: "Reads payslips, receipts, bank statements, CAC certificates, prior filings.",
  },
  {
    no: "03",
    name: "Calculator & Optimizer",
    body: "PIT, CIT, VAT, WHT, PAYE, Development Levy — every pure-math liability, in Decimal.",
  },
  {
    no: "04",
    name: "Compliance Advisor",
    body: "24-hour MBS sync window, ₦100m VAT threshold, 55-field rule — flagged proactively.",
  },
  {
    no: "05",
    name: "Explanation Engine",
    body: "Tax jargon translated to plain English / Hausa / Yorùbá / Igbo / Naijá.",
  },
  {
    no: "06",
    name: "Audit Shield",
    body: "Pre-filing review — catches missing fields and schema violations before NRS does.",
  },
  {
    no: "07",
    name: "Filing Orchestrator",
    body: "Generates downloadable packs today; OAuth2 + HMAC handshake with NRS for live submissions.",
  },
  {
    no: "08",
    name: "Learning Partner",
    body: "Year-over-year memory, anomalies, mid-year nudges so next year's return starts smarter.",
  },
  {
    no: "09",
    name: "Receipt & E-Invoice Co-Pilot",
    body: "For SMEs: MBS-compliant e-invoices with QR + CSID + IRN.",
  },
  {
    no: "10",
    name: "Multi-Agent Orchestrator",
    body: "Mai routes work to Calculator, Verifier, Filer, Reviewer sub-agents via tool use.",
  },
];

interface Persona {
  who: string;
  fits: string;
  flow: string;
  link: { href: string; label: string };
}

const PERSONAS: Persona[] = [
  {
    who: "Individuals (PAYE / freelancer / multi-income)",
    fits:
      "Salary, side income, rental, investments. PIT 2026 bands, reliefs, PAYE reconciliation, audit-ready PDF + JSON.",
    flow: "Chat → upload payslip → confirm reliefs → Audit Shield → download pack.",
    link: { href: "/chat", label: "Start with Mai" },
  },
  {
    who: "SMEs (LTD, PLC, BN)",
    fits:
      "Corporate Income Tax, WHT remittance, VAT threshold tracking, MBS e-invoicing (preview). 2026 CIT bands flagged as illustrative until NRS confirms.",
    flow:
      "Verify CAC RC → enter revenues + expenses → CIT computation → Audit Shield → corporate filing pack.",
    link: { href: "/sme", label: "Open SME / corporate" },
  },
  {
    who: "NGOs (Incorporated Trustees, CAC Part-C)",
    fits:
      "Annual exempt-body return: income, expenditure, WHT remitted on payments made. Exemption-status declaration + signatory affirmation.",
    flow: "Trustee onboarding → income + expenditure blocks → WHT schedule → audit → annual pack.",
    link: { href: "/ngo", label: "Open NGO intake" },
  },
];

interface StatusRow {
  label: string;
  state: "ready" | "partial" | "pending";
  note: string;
}

const READINESS: StatusRow[] = [
  { label: "PIT (individual) calculator + audit + pack", state: "ready", note: "2026 bands tested." },
  { label: "PAYE / VAT / Development Levy calculators", state: "ready", note: "Pure-math, Decimal precision." },
  { label: "CIT (corporate) calculator + flow", state: "partial", note: "Math works; 2026 rates illustrative until owner confirms." },
  { label: "NGO annual return + audit + pack", state: "partial", note: "Schema + audit live; PDF uses interim renderer." },
  { label: "Document upload + Vision extraction", state: "ready", note: "Needs Anthropic API key." },
  { label: "NIN + CAC verification", state: "partial", note: "Dojah integration ready; needs vendor credentials." },
  { label: "Year-over-year memory + anomalies + nudges", state: "ready", note: "DB-backed; surfaces in /dashboard." },
  { label: "Multilingual UI (en / ha / yo / ig / pcm)", state: "ready", note: "ADR-0004; payloads stay English by regulation." },
  { label: "Live NRS submission (Rev360)", state: "pending", note: "Simulated today; unlocks with sandbox credentials." },
  { label: "MBS 24-hour sync (Phase 9.4)", state: "pending", note: "Celery scaffolded; awaits Redis + APP partner URL." },
  { label: "UBL 3.0 e-invoice composer with QR / CSID UI", state: "pending", note: "Backend math ready; UI lands once 55-field paths are confirmed." },
];

const STATE_STYLES: Record<StatusRow["state"], string> = {
  ready: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  partial: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  pending: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
};

const STATE_LABEL: Record<StatusRow["state"], string> = {
  ready: "Live",
  partial: "Partial",
  pending: "Coming",
};

export default function HowItWorksPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-12 sm:py-16">
      {/* Hero */}
      <header className="space-y-4">
        <span className="inline-block rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200">
          How it works
        </span>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight sm:text-4xl">
          File your Nigerian taxes by talking, not by filling forms.
        </h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Mai Filer is an AI-native peer to TurboTax and TaxSlayer, built for
          Nigeria&apos;s 2026 tax reform. She walks you through your filing in
          your own language, reads your documents, does the math, runs an
          audit, and gives you an NRS-ready pack — all in one conversation.
        </p>
      </header>

      {/* The 5-step flow */}
      <section aria-labelledby="flow-heading" className="space-y-4">
        <h2
          id="flow-heading"
          className="text-sm font-semibold uppercase tracking-wider text-zinc-500"
        >
          A filing in five steps
        </h2>
        <ol className="space-y-4">
          {STEPS.map((step) => (
            <li
              key={step.no}
              className="flex gap-4 rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800"
            >
              <span
                aria-hidden="true"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-sm font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900"
              >
                {step.no}
              </span>
              <div className="space-y-1">
                <h3 className="font-medium">{step.title}</h3>
                <p className="text-sm text-zinc-600 dark:text-zinc-400">
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* The 10 BIG Roles */}
      <section aria-labelledby="roles-heading" className="space-y-4">
        <h2
          id="roles-heading"
          className="text-sm font-semibold uppercase tracking-wider text-zinc-500"
        >
          What Mai actually does — ten responsibilities
        </h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Mai isn&apos;t a chatbot bolted onto a form wizard. She&apos;s a
          multi-agent orchestrator with ten standing roles, each backed by
          dedicated tools:
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {ROLES.map((role) => (
            <div
              key={role.no}
              className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
            >
              <div className="font-mono text-xs text-zinc-400">{role.no}</div>
              <div className="mt-1 font-medium">{role.name}</div>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                {role.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* For whom */}
      <section aria-labelledby="personas-heading" className="space-y-4">
        <h2
          id="personas-heading"
          className="text-sm font-semibold uppercase tracking-wider text-zinc-500"
        >
          Built for three kinds of taxpayer
        </h2>
        <div className="space-y-3">
          {PERSONAS.map((p) => (
            <article
              key={p.who}
              className="space-y-2 rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800"
            >
              <h3 className="font-medium">{p.who}</h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{p.fits}</p>
              <p className="text-sm">
                <span className="font-mono text-xs text-zinc-500">FLOW · </span>
                {p.flow}
              </p>
              <Link
                href={p.link.href}
                className="inline-flex items-center text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-300"
              >
                {p.link.label} →
              </Link>
            </article>
          ))}
        </div>
      </section>

      {/* Honest readiness */}
      <section aria-labelledby="readiness-heading" className="space-y-4">
        <h2
          id="readiness-heading"
          className="text-sm font-semibold uppercase tracking-wider text-zinc-500"
        >
          What&apos;s live today, what&apos;s next
        </h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Tax software hides what doesn&apos;t work. We don&apos;t. Here&apos;s
          the honest map of every feature&apos;s state.
        </p>
        <ul className="divide-y divide-zinc-200 rounded-2xl border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {READINESS.map((row) => (
            <li
              key={row.label}
              className="flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4"
            >
              <div className="flex-1">
                <div className="font-medium">{row.label}</div>
                <div className="text-sm text-zinc-600 dark:text-zinc-400">
                  {row.note}
                </div>
              </div>
              <span
                className={`inline-flex w-fit shrink-0 items-center rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${
                  STATE_STYLES[row.state]
                }`}
              >
                {STATE_LABEL[row.state]}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* Stack + compliance */}
      <section aria-labelledby="trust-heading" className="space-y-4">
        <h2
          id="trust-heading"
          className="text-sm font-semibold uppercase tracking-wider text-zinc-500"
        >
          Built carefully
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h3 className="font-medium">Claude-native reasoning</h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Claude Opus 4.7 orchestrates Mai; Sonnet 4.6 handles document
              vision; Haiku 4.5 handles cheap classification. Prompt caching
              keeps costs honest.
            </p>
          </div>
          <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h3 className="font-medium">NDPR + NITDA-aware</h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Consent captured before every NIN query. Raw NIN never stored —
              only a hash + Fernet-encrypted ciphertext. Append-only consent
              log per query.
            </p>
          </div>
          <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h3 className="font-medium">Decimal precision throughout</h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Every naira / kobo amount is computed in Decimal — no
              floating-point drift. Pack files are byte-stable for two
              identical inputs.
            </p>
          </div>
          <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h3 className="font-medium">Quarantined placeholders</h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Where 2026 statutory data is still being confirmed by NRS, the
              code refuses to ship wrong numbers silently — every CIT / WHT /
              UBL response is loudly flagged{" "}
              <span className="font-mono">statutory_is_placeholder=true</span>.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="flex flex-col gap-3 border-t border-zinc-200 pt-8 dark:border-zinc-800 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Ready to start a conversation with Mai?
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/chat"
            className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            Start chatting →
          </Link>
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-zinc-300 px-5 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            Back home
          </Link>
        </div>
      </section>
    </main>
  );
}
