"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  API_BASE,
  CITResult,
  CITReturn,
  CorporateCompanyType,
  CorporateExpenseKind,
  CorporateFilingRecord,
  WHTResult,
  calcCit,
  calcWht,
  createCorporateFiling,
  listWhtClasses,
} from "@/lib/api";
import {
  LANGUAGE_CODES,
  LANGUAGE_LABELS,
  LanguageCode,
  getMessages,
} from "@/lib/messages";

const DEFAULT_ENVELOPE = `{
  "version": "ubl-3.0",
  "profile": "urn:mai-filer:ubl-3.0:mbs-einvoice-v1",
  "sections": []
}`;

const COMPANY_TYPES: CorporateCompanyType[] = ["LTD", "PLC", "BN", "LLP", "OTHER"];
const EXPENSE_KINDS: CorporateExpenseKind[] = [
  "cost_of_sales",
  "salaries_wages",
  "rent",
  "utilities",
  "depreciation",
  "professional_fees",
  "marketing",
  "interest",
  "other",
];

interface RevenueRow {
  label: string;
  amount: string;
}

interface ExpenseRow {
  kind: CorporateExpenseKind;
  label: string;
  amount: string;
}

function emptyRevenueRow(): RevenueRow {
  return { label: "Sales", amount: "0" };
}

function emptyExpenseRow(): ExpenseRow {
  return { kind: "cost_of_sales", label: "", amount: "0" };
}

export default function SmePage() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const t = useMemo(() => getMessages(language), [language]);
  const router = useRouter();

  // CIT calculator inputs
  const [turnover, setTurnover] = useState("50000000");
  const [profit, setProfit] = useState("10000000");
  const [includeTertiary, setIncludeTertiary] = useState(true);
  const [citResult, setCitResult] = useState<CITResult | null>(null);
  const [citBusy, setCitBusy] = useState(false);

  // WHT inputs
  const [whtGross, setWhtGross] = useState("1000000");
  const [whtClass, setWhtClass] = useState("rent");
  const [whtClasses, setWhtClasses] = useState<string[]>(["rent"]);
  const [whtResult, setWhtResult] = useState<WHTResult | null>(null);
  const [whtBusy, setWhtBusy] = useState(false);

  // UBL envelope
  const [envelopeJson, setEnvelopeJson] = useState(DEFAULT_ENVELOPE);
  const [ublResult, setUblResult] = useState<
    null | {
      ok: boolean;
      section_count: number;
      field_count: number;
      findings: Array<{
        code: string;
        severity: string;
        message: string;
        path: string | null;
      }>;
      statutory_is_placeholder: boolean;
      error?: string;
    }
  >(null);
  const [ublBusy, setUblBusy] = useState(false);

  const [error, setError] = useState<string | null>(null);

  // ----- Corporate filing intake ------------------------------------------
  const thisYear = new Date().getUTCFullYear();
  const [taxYear, setTaxYear] = useState(thisYear);
  const [periodStart, setPeriodStart] = useState(`${thisYear}-01-01`);
  const [periodEnd, setPeriodEnd] = useState(`${thisYear}-12-31`);
  const [rc, setRc] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyType, setCompanyType] = useState<CorporateCompanyType>("LTD");
  const [tin, setTin] = useState("");
  const [industry, setIndustry] = useState("");
  const [regAddress, setRegAddress] = useState("");
  const [compEmail, setCompEmail] = useState("");
  const [compPhone, setCompPhone] = useState("");
  const [officerName, setOfficerName] = useState("");
  const [officerNin, setOfficerNin] = useState("");
  const [revenues, setRevenues] = useState<RevenueRow[]>([emptyRevenueRow()]);
  const [expenses, setExpenses] = useState<ExpenseRow[]>([emptyExpenseRow()]);
  const [declaredTurnover, setDeclaredTurnover] = useState("");
  const [whtSuffered, setWhtSuffered] = useState("0");
  const [advanceTax, setAdvanceTax] = useState("0");
  const [corpDeclaration, setCorpDeclaration] = useState(false);
  const [corpBusy, setCorpBusy] = useState(false);
  const [corpCreated, setCorpCreated] =
    useState<CorporateFilingRecord | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const resp = await listWhtClasses();
        if (resp.classes.length) {
          setWhtClasses(resp.classes);
          if (!resp.classes.includes(whtClass)) setWhtClass(resp.classes[0]);
        }
      } catch {
        // Leave defaults if the API is unreachable in dev.
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canSubmitCorp =
    rc.trim().length > 0 &&
    companyName.trim().length >= 2 &&
    corpDeclaration &&
    !corpBusy;

  async function runCit(e: React.FormEvent) {
    e.preventDefault();
    setCitBusy(true);
    setError(null);
    try {
      const res = await calcCit({
        annual_turnover: turnover,
        assessable_profit: profit,
        include_tertiary: includeTertiary,
      });
      setCitResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCitBusy(false);
    }
  }

  async function runWht(e: React.FormEvent) {
    e.preventDefault();
    setWhtBusy(true);
    setError(null);
    try {
      const res = await calcWht({ gross_amount: whtGross, transaction_class: whtClass });
      setWhtResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setWhtBusy(false);
    }
  }

  async function runUblValidate() {
    setUblBusy(true);
    setError(null);
    setUblResult(null);
    try {
      let payload: unknown;
      try {
        payload = JSON.parse(envelopeJson);
      } catch (err) {
        setUblResult({
          ok: false,
          section_count: 0,
          field_count: 0,
          findings: [],
          statutory_is_placeholder: true,
          error: err instanceof Error ? err.message : "invalid JSON",
        });
        return;
      }
      const resp = await fetch(`${API_BASE}/v1/sme/validate-ubl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ envelope: payload }),
      });
      const body = await resp.json();
      setUblResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUblBusy(false);
    }
  }

  async function submitCorporate(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmitCorp) return;
    setCorpBusy(true);
    setError(null);
    setCorpCreated(null);
    const body: CITReturn = {
      tax_year: taxYear,
      period_start: periodStart,
      period_end: periodEnd,
      taxpayer: {
        rc_number: rc.trim(),
        company_name: companyName.trim(),
        company_type: companyType,
        tin: tin || null,
        registered_address: regAddress || null,
        industry: industry || null,
        email: compEmail || null,
        phone: compPhone || null,
        primary_officer_name: officerName || null,
        primary_officer_nin: officerNin || null,
      },
      revenues: revenues
        .filter((r) => r.label.trim() && r.amount !== "")
        .map((r) => ({ label: r.label, amount: r.amount })),
      expenses: expenses
        .filter((e) => e.label.trim() && e.amount !== "")
        .map((e) => ({ kind: e.kind, label: e.label, amount: e.amount })),
      declared_turnover: declaredTurnover || null,
      wht_already_suffered: whtSuffered || "0",
      advance_tax_paid: advanceTax || "0",
      declaration: corpDeclaration,
    };
    try {
      const record = await createCorporateFiling(body);
      setCorpCreated(record);
      router.push(`/corporate-filings/${record.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCorpBusy(false);
    }
  }

  function updateRevenue(idx: number, patch: Partial<RevenueRow>) {
    setRevenues((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    );
  }

  function updateExpense(idx: number, patch: Partial<ExpenseRow>) {
    setExpenses((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    );
  }

  function money(value: string | undefined): string {
    if (!value) return "—";
    const n = Number(value);
    if (Number.isNaN(n)) return value;
    return `₦${n.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">Phase 9 preview</p>
          <h1 className="mt-1 text-2xl font-semibold sm:text-3xl">{t.sme.title}</h1>
          <p className="mt-1 text-sm text-zinc-500">{t.sme.subtitle}</p>
        </div>
        <label htmlFor="sme-language" className="flex items-center gap-2 text-sm">
          <span className="text-zinc-500">{t.chat.language}</span>
          <select
            id="sme-language"
            className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={language}
            onChange={(e) => setLanguage(e.target.value as LanguageCode)}
          >
            {LANGUAGE_CODES.map((code) => (
              <option key={code} value={code}>{LANGUAGE_LABELS[code]}</option>
            ))}
          </select>
        </label>
      </header>

      <aside
        role="note"
        className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
      >
        ⚠️ {t.sme.placeholderBanner}
      </aside>

      {error ? (
        <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          {error}
        </p>
      ) : null}

      {/* Corporate filing intake --------------------------------------- */}
      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          File a CIT return
        </h2>
        <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
          Start a Corporate Income Tax return for your company. CAC Part-A
          RC is the primary identifier — verify it via the chat flow first
          if you haven&apos;t already. Computations run against the
          placeholder 2026 bands until the owner confirms the real schedule.
        </p>
        <form onSubmit={submitCorporate} className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="corp-rc" label="CAC RC number" value={rc} onChange={setRc} required />
            <Field id="corp-name" label="Company name" value={companyName} onChange={setCompanyName} required />
            <div>
              <label htmlFor="corp-type" className="block text-xs text-zinc-500">Company type</label>
              <select
                id="corp-type"
                value={companyType}
                onChange={(e) => setCompanyType(e.target.value as CorporateCompanyType)}
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              >
                {COMPANY_TYPES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <Field id="corp-tin" label="TIN (optional)" value={tin} onChange={setTin} />
            <Field id="corp-industry" label="Industry" value={industry} onChange={setIndustry} />
            <Field id="corp-address" label="Registered address" value={regAddress} onChange={setRegAddress} />
            <Field id="corp-email" label="Email" value={compEmail} onChange={setCompEmail} type="email" />
            <Field id="corp-phone" label="Phone" value={compPhone} onChange={setCompPhone} />
            <NumField
              id="corp-year"
              label="Tax year"
              value={String(taxYear)}
              onChange={(v) => setTaxYear(Number(v))}
              min={2025}
              max={2100}
            />
            <Field id="corp-pstart" label="Period start" value={periodStart} onChange={setPeriodStart} type="date" />
            <Field id="corp-pend" label="Period end" value={periodEnd} onChange={setPeriodEnd} type="date" />
            <Field id="corp-officer-name" label="Primary officer name" value={officerName} onChange={setOfficerName} />
            <Field id="corp-officer-nin" label="Primary officer NIN" value={officerNin} onChange={setOfficerNin} />
          </div>

          <fieldset className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <legend className="px-2 text-xs uppercase tracking-wider text-zinc-500">Revenues</legend>
            <div className="space-y-2">
              {revenues.map((row, idx) => (
                <div key={idx} className="grid gap-2 sm:grid-cols-5">
                  <Field
                    id={`rev-label-${idx}`}
                    label="Label"
                    value={row.label}
                    onChange={(v) => updateRevenue(idx, { label: v })}
                    className="sm:col-span-3"
                  />
                  <NumField
                    id={`rev-amount-${idx}`}
                    label="Amount (₦)"
                    value={row.amount}
                    onChange={(v) => updateRevenue(idx, { amount: v })}
                    className="sm:col-span-2"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() => setRevenues((p) => [...p, emptyRevenueRow()])}
                className="rounded-full border border-zinc-300 px-3 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                + Add revenue line
              </button>
            </div>
          </fieldset>

          <fieldset className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <legend className="px-2 text-xs uppercase tracking-wider text-zinc-500">Expenses</legend>
            <div className="space-y-2">
              {expenses.map((row, idx) => (
                <div key={idx} className="grid gap-2 sm:grid-cols-6">
                  <div className="sm:col-span-2">
                    <label htmlFor={`exp-kind-${idx}`} className="block text-xs text-zinc-500">Kind</label>
                    <select
                      id={`exp-kind-${idx}`}
                      value={row.kind}
                      onChange={(e) =>
                        updateExpense(idx, {
                          kind: e.target.value as CorporateExpenseKind,
                        })
                      }
                      className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    >
                      {EXPENSE_KINDS.map((k) => (
                        <option key={k} value={k}>{k.replace(/_/g, " ")}</option>
                      ))}
                    </select>
                  </div>
                  <Field
                    id={`exp-label-${idx}`}
                    label="Label"
                    value={row.label}
                    onChange={(v) => updateExpense(idx, { label: v })}
                    className="sm:col-span-2"
                  />
                  <NumField
                    id={`exp-amount-${idx}`}
                    label="Amount (₦)"
                    value={row.amount}
                    onChange={(v) => updateExpense(idx, { amount: v })}
                    className="sm:col-span-2"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() => setExpenses((p) => [...p, emptyExpenseRow()])}
                className="rounded-full border border-zinc-300 px-3 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                + Add expense line
              </button>
            </div>
          </fieldset>

          <div className="grid gap-3 sm:grid-cols-3">
            <NumField
              id="corp-declared-turnover"
              label="Declared turnover (optional, overrides sum)"
              value={declaredTurnover}
              onChange={setDeclaredTurnover}
            />
            <NumField
              id="corp-wht-suffered"
              label="WHT already suffered"
              value={whtSuffered}
              onChange={setWhtSuffered}
            />
            <NumField
              id="corp-advance"
              label="Advance tax paid"
              value={advanceTax}
              onChange={setAdvanceTax}
            />
          </div>

          <fieldset className="rounded-xl bg-amber-50 p-4 text-sm dark:bg-amber-950/40">
            <label className="flex items-start gap-2 text-amber-900 dark:text-amber-200">
              <input
                type="checkbox"
                className="mt-1"
                checked={corpDeclaration}
                onChange={(e) => setCorpDeclaration(e.target.checked)}
              />
              <span>
                I am an authorised officer and affirm this CIT return is
                true, correct, and complete to the best of my knowledge.
              </span>
            </label>
          </fieldset>

          <button
            type="submit"
            disabled={!canSubmitCorp}
            className="w-full rounded-full bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-40 sm:w-auto"
          >
            {corpBusy ? "Submitting…" : "Create CIT filing"}
          </button>

          {corpCreated ? (
            <p className="text-sm text-emerald-800 dark:text-emerald-200">
              Created filing{" "}
              <Link className="font-mono underline" href={`/corporate-filings/${corpCreated.id}`}>
                {corpCreated.id}
              </Link>
              .
            </p>
          ) : null}
        </form>
      </section>

      {/* CIT calculator (quick preview, does not persist) -------------- */}
      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.sme.citHeading}
        </h2>
        <form onSubmit={runCit} className="grid gap-3 sm:grid-cols-2">
          <label htmlFor="sme-cit-turnover" className="block text-xs text-zinc-500">
            {t.sme.citTurnoverLabel}
            <input
              id="sme-cit-turnover"
              type="number"
              min={0}
              step={100000}
              value={turnover}
              onChange={(e) => setTurnover(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <label htmlFor="sme-cit-profit" className="block text-xs text-zinc-500">
            {t.sme.citProfitLabel}
            <input
              id="sme-cit-profit"
              type="number"
              min={0}
              step={100000}
              value={profit}
              onChange={(e) => setProfit(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <label className="sm:col-span-2 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeTertiary}
              onChange={(e) => setIncludeTertiary(e.target.checked)}
            />
            {t.sme.citIncludeTertiary}
          </label>
          <button
            type="submit"
            disabled={citBusy}
            className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 sm:col-span-2 sm:w-fit"
          >
            {citBusy ? "…" : t.sme.citCalculate}
          </button>
        </form>
        {citResult ? (
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <Row label={t.sme.citResultTier} value={citResult.tier} />
            <Row label={t.sme.citResultCit} value={money(citResult.cit_amount)} />
            <Row label={t.sme.citResultTertiary} value={money(citResult.tertiary_amount)} />
            <Row
              label={t.sme.citResultTotal}
              value={<strong>{money(citResult.total_payable)}</strong>}
            />
          </dl>
        ) : null}
      </section>

      {/* WHT */}
      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.sme.whtHeading}
        </h2>
        <form onSubmit={runWht} className="grid gap-3 sm:grid-cols-2">
          <label htmlFor="sme-wht-gross" className="block text-xs text-zinc-500">
            {t.sme.whtGrossLabel}
            <input
              id="sme-wht-gross"
              type="number"
              min={0}
              step={1000}
              value={whtGross}
              onChange={(e) => setWhtGross(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <label htmlFor="sme-wht-class" className="block text-xs text-zinc-500">
            {t.sme.whtClassLabel}
            <select
              id="sme-wht-class"
              value={whtClass}
              onChange={(e) => setWhtClass(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            >
              {whtClasses.map((c) => (
                <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={whtBusy}
            className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 sm:col-span-2 sm:w-fit"
          >
            {whtBusy ? "…" : t.sme.whtCalculate}
          </button>
        </form>
        {whtResult ? (
          whtResult.error ? (
            <p className="mt-4 rounded-md bg-rose-50 p-3 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
              {whtResult.error}
            </p>
          ) : (
            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              <Row label={t.sme.whtResultAmount} value={money(whtResult.wht_amount)} />
              <Row label={t.sme.whtResultNet} value={money(whtResult.net_payable)} />
            </dl>
          )
        ) : null}
      </section>

      {/* UBL */}
      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.sme.ublHeading}
        </h2>
        <p className="mb-2 text-xs text-zinc-500">{t.sme.ublHelp}</p>
        <label htmlFor="sme-ubl-input" className="sr-only">
          {t.sme.ublHeading}
        </label>
        <textarea
          id="sme-ubl-input"
          value={envelopeJson}
          onChange={(e) => setEnvelopeJson(e.target.value)}
          rows={10}
          className="w-full rounded-md border border-zinc-300 bg-white p-3 font-mono text-xs focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
        />
        <button
          type="button"
          onClick={() => void runUblValidate()}
          disabled={ublBusy}
          className="mt-3 rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {ublBusy ? "…" : t.sme.ublValidate}
        </button>
        {ublResult ? (
          <div
            className={`mt-4 rounded-lg border p-3 text-sm ${
              ublResult.ok
                ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
                : "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
            }`}
          >
            <p className="font-medium">
              {ublResult.ok ? `✅ ${t.sme.ublOk}` : `❌ ${t.sme.ublFail}`}
            </p>
            {ublResult.error ? (
              <p className="mt-1">{ublResult.error}</p>
            ) : (
              <p className="mt-1 text-xs">
                {ublResult.section_count} / 8 sections · {ublResult.field_count} / 55 fields
              </p>
            )}
            {ublResult.findings && ublResult.findings.length > 0 ? (
              <ul className="mt-2 space-y-1 text-xs">
                {ublResult.findings.slice(0, 20).map((f, i) => (
                  <li key={i} className="font-mono">
                    [{f.severity.toUpperCase()}] {f.code} — {f.message}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </section>

      <footer className="pt-2 text-sm">
        <Link href="/chat" className="text-zinc-500 hover:underline">
          ← {t.dashboard.backToChat}
        </Link>
      </footer>
    </main>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

interface FieldCtlProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  type?: string;
  className?: string;
}

function Field(props: FieldCtlProps) {
  return (
    <div className={props.className}>
      <label htmlFor={props.id} className="block text-xs text-zinc-500">
        {props.label}
      </label>
      <input
        id={props.id}
        type={props.type ?? "text"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        required={props.required}
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
      />
    </div>
  );
}

function NumField(props: FieldCtlProps & { min?: number; max?: number; step?: number }) {
  return (
    <div className={props.className}>
      <label htmlFor={props.id} className="block text-xs text-zinc-500">
        {props.label}
      </label>
      <input
        id={props.id}
        type="number"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        min={props.min}
        max={props.max}
        step={props.step ?? 1}
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
      />
    </div>
  );
}
