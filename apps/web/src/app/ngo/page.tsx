"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  NgoFilingRecord,
  NgoPurpose,
  NgoReturn,
  NgoWhtRecipient,
  createNgoFiling,
} from "@/lib/api";
import {
  LANGUAGE_CODES,
  LANGUAGE_LABELS,
  LanguageCode,
  getMessages,
} from "@/lib/messages";

const PURPOSES: NgoPurpose[] = [
  "charitable",
  "educational",
  "religious",
  "scientific",
  "cultural",
  "social_welfare",
  "other",
];

const WHT_RECIPIENTS: NgoWhtRecipient[] = [
  "individual",
  "corporate",
  "partnership",
  "foreign_entity",
  "other",
];

interface WhtRow {
  period_month: number;
  transaction_class: string;
  recipient_category: NgoWhtRecipient;
  gross_amount: string;
  wht_amount: string;
  remittance_receipt: string;
}

function emptyRow(): WhtRow {
  return {
    period_month: 1,
    transaction_class: "rent",
    recipient_category: "corporate",
    gross_amount: "0",
    wht_amount: "0",
    remittance_receipt: "",
  };
}

export default function NgoIntakePage() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const t = useMemo(() => getMessages(language), [language]);

  // Identity
  const [rc, setRc] = useState("");
  const [legalName, setLegalName] = useState("");
  const [tradeName, setTradeName] = useState("");
  const [purpose, setPurpose] = useState<NgoPurpose>("charitable");
  const [address, setAddress] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [exemptionRef, setExemptionRef] = useState("");

  // Period
  const thisYear = new Date().getUTCFullYear();
  const [taxYear, setTaxYear] = useState(thisYear);
  const [periodStart, setPeriodStart] = useState(`${thisYear}-01-01`);
  const [periodEnd, setPeriodEnd] = useState(`${thisYear}-12-31`);

  // Income
  const [localDonations, setLocalDonations] = useState("0");
  const [foreignDonations, setForeignDonations] = useState("0");
  const [govGrants, setGovGrants] = useState("0");
  const [foundationGrants, setFoundationGrants] = useState("0");
  const [programIncome, setProgramIncome] = useState("0");
  const [investmentIncome, setInvestmentIncome] = useState("0");
  const [otherIncome, setOtherIncome] = useState("0");

  // Expenditure
  const [programExpenses, setProgramExpenses] = useState("0");
  const [adminExpenses, setAdminExpenses] = useState("0");
  const [fundraisingExpenses, setFundraisingExpenses] = useState("0");
  const [otherExpenses, setOtherExpenses] = useState("0");

  // WHT
  const [whtRows, setWhtRows] = useState<WhtRow[]>([emptyRow()]);

  // Declarations
  const [exemptionAffirmed, setExemptionAffirmed] = useState(false);
  const [declarationAffirmed, setDeclarationAffirmed] = useState(false);

  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState<NgoFilingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canSubmit =
    rc.length > 0 &&
    legalName.trim().length >= 2 &&
    exemptionAffirmed &&
    declarationAffirmed &&
    !busy;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setCreated(null);
    const body: NgoReturn = {
      tax_year: taxYear,
      period_start: periodStart,
      period_end: periodEnd,
      organization: {
        cac_part_c_rc: rc,
        legal_name: legalName,
        trade_name: tradeName || null,
        exemption_reference: exemptionRef || null,
        purpose,
        registered_address: address || null,
        email: email || null,
        phone: phone || null,
      },
      income: {
        local_donations: localDonations,
        foreign_donations: foreignDonations,
        government_grants: govGrants,
        foundation_grants: foundationGrants,
        program_income: programIncome,
        investment_income: investmentIncome,
        other_income: otherIncome,
      },
      expenditure: {
        program_expenses: programExpenses,
        administrative: adminExpenses,
        fundraising: fundraisingExpenses,
        other: otherExpenses,
      },
      wht_schedule: whtRows.map((row) => ({
        period_month: row.period_month,
        transaction_class: row.transaction_class,
        recipient_category: row.recipient_category,
        gross_amount: row.gross_amount,
        wht_amount: row.wht_amount,
        remittance_receipt: row.remittance_receipt || null,
      })),
      exemption_status_declaration: exemptionAffirmed,
      declaration: declarationAffirmed,
    };
    try {
      const record = await createNgoFiling(body);
      setCreated(record);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function updateWhtRow(idx: number, patch: Partial<WhtRow>) {
    setWhtRows((prev) =>
      prev.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    );
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8 sm:py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            Phase 11
          </p>
          <h1 className="mt-1 text-2xl font-semibold sm:text-3xl">
            {t.ngo.title}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">{t.ngo.subtitle}</p>
        </div>
        <label
          htmlFor="ngo-language"
          className="flex items-center gap-2 text-sm"
        >
          <span className="text-zinc-500">{t.chat.language}</span>
          <select
            id="ngo-language"
            className="rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={language}
            onChange={(e) => setLanguage(e.target.value as LanguageCode)}
            disabled={busy}
          >
            {LANGUAGE_CODES.map((code) => (
              <option key={code} value={code}>
                {LANGUAGE_LABELS[code]}
              </option>
            ))}
          </select>
        </label>
      </header>

      <aside
        role="note"
        className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
      >
        ⚠️ {t.ngo.placeholderBanner}
      </aside>

      <form onSubmit={submit} className="space-y-8">
        {/* Organisation */}
        <Section title={t.ngo.sectionOrgTitle}>
          <Grid>
            <TextField id="ngo-rc" label={t.ngo.rcLabel} value={rc} onChange={setRc} helperId="ngo-rc-help" helper={t.ngo.rcHelper} required />
            <TextField id="ngo-legal" label={t.ngo.legalNameLabel} value={legalName} onChange={setLegalName} required />
            <TextField id="ngo-trade" label={t.ngo.tradeNameLabel} value={tradeName} onChange={setTradeName} />
            <div>
              <label htmlFor="ngo-purpose" className="block text-xs text-zinc-500">
                {t.ngo.purposeLabel}
              </label>
              <select
                id="ngo-purpose"
                className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value as NgoPurpose)}
              >
                {PURPOSES.map((p) => (
                  <option key={p} value={p}>{p.replace("_", " ")}</option>
                ))}
              </select>
            </div>
            <TextField id="ngo-exref" label={t.ngo.exemptionRefLabel} value={exemptionRef} onChange={setExemptionRef} />
            <TextField id="ngo-address" label={t.ngo.addressLabel} value={address} onChange={setAddress} />
            <TextField id="ngo-email" label={t.ngo.emailLabel} type="email" value={email} onChange={setEmail} />
            <TextField id="ngo-phone" label={t.ngo.phoneLabel} value={phone} onChange={setPhone} />
            <NumberField id="ngo-year" label={t.ngo.taxYearLabel} value={String(taxYear)} onChange={(v) => setTaxYear(Number(v))} min={2025} max={2100} />
            <TextField id="ngo-period-start" label={t.ngo.periodStartLabel} type="date" value={periodStart} onChange={setPeriodStart} />
            <TextField id="ngo-period-end" label={t.ngo.periodEndLabel} type="date" value={periodEnd} onChange={setPeriodEnd} />
          </Grid>
        </Section>

        {/* Income */}
        <Section title={t.ngo.sectionIncomeTitle}>
          <Grid>
            <NumberField id="ngo-income-local" label={t.ngo.incomeLocalDonations} value={localDonations} onChange={setLocalDonations} />
            <NumberField id="ngo-income-foreign" label={t.ngo.incomeForeignDonations} value={foreignDonations} onChange={setForeignDonations} />
            <NumberField id="ngo-income-gov" label={t.ngo.incomeGovGrants} value={govGrants} onChange={setGovGrants} />
            <NumberField id="ngo-income-foundation" label={t.ngo.incomeFoundationGrants} value={foundationGrants} onChange={setFoundationGrants} />
            <NumberField id="ngo-income-program" label={t.ngo.incomeProgram} value={programIncome} onChange={setProgramIncome} />
            <NumberField id="ngo-income-investment" label={t.ngo.incomeInvestment} value={investmentIncome} onChange={setInvestmentIncome} />
            <NumberField id="ngo-income-other" label={t.ngo.incomeOther} value={otherIncome} onChange={setOtherIncome} />
          </Grid>
        </Section>

        {/* Expenditure */}
        <Section title={t.ngo.sectionExpenditureTitle}>
          <Grid>
            <NumberField id="ngo-exp-program" label={t.ngo.expProgram} value={programExpenses} onChange={setProgramExpenses} />
            <NumberField id="ngo-exp-admin" label={t.ngo.expAdmin} value={adminExpenses} onChange={setAdminExpenses} />
            <NumberField id="ngo-exp-fundraising" label={t.ngo.expFundraising} value={fundraisingExpenses} onChange={setFundraisingExpenses} />
            <NumberField id="ngo-exp-other" label={t.ngo.expOther} value={otherExpenses} onChange={setOtherExpenses} />
          </Grid>
        </Section>

        {/* WHT schedule */}
        <Section title={t.ngo.sectionWhtTitle}>
          <div className="space-y-3">
            {whtRows.map((row, idx) => (
              <div
                key={idx}
                className="grid grid-cols-1 gap-2 rounded-lg border border-zinc-200 p-3 sm:grid-cols-6 dark:border-zinc-800"
              >
                <NumberField
                  id={`ngo-wht-month-${idx}`}
                  label={t.ngo.whtMonthLabel}
                  value={String(row.period_month)}
                  onChange={(v) => updateWhtRow(idx, { period_month: Number(v) })}
                  min={1}
                  max={12}
                />
                <TextField
                  id={`ngo-wht-class-${idx}`}
                  label={t.ngo.whtClassLabel}
                  value={row.transaction_class}
                  onChange={(v) => updateWhtRow(idx, { transaction_class: v })}
                />
                <div>
                  <label htmlFor={`ngo-wht-recipient-${idx}`} className="block text-xs text-zinc-500">
                    {t.ngo.whtRecipientLabel}
                  </label>
                  <select
                    id={`ngo-wht-recipient-${idx}`}
                    className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                    value={row.recipient_category}
                    onChange={(e) =>
                      updateWhtRow(idx, {
                        recipient_category: e.target.value as NgoWhtRecipient,
                      })
                    }
                  >
                    {WHT_RECIPIENTS.map((r) => (
                      <option key={r} value={r}>{r.replace("_", " ")}</option>
                    ))}
                  </select>
                </div>
                <NumberField
                  id={`ngo-wht-gross-${idx}`}
                  label={t.ngo.whtGrossLabel}
                  value={row.gross_amount}
                  onChange={(v) => updateWhtRow(idx, { gross_amount: v })}
                />
                <NumberField
                  id={`ngo-wht-amount-${idx}`}
                  label={t.ngo.whtAmountLabel}
                  value={row.wht_amount}
                  onChange={(v) => updateWhtRow(idx, { wht_amount: v })}
                />
                <TextField
                  id={`ngo-wht-receipt-${idx}`}
                  label={t.ngo.whtReceiptLabel}
                  value={row.remittance_receipt}
                  onChange={(v) => updateWhtRow(idx, { remittance_receipt: v })}
                />
                {whtRows.length > 1 ? (
                  <button
                    type="button"
                    onClick={() =>
                      setWhtRows((prev) => prev.filter((_, i) => i !== idx))
                    }
                    className="col-span-full justify-self-end text-xs text-rose-700 hover:underline dark:text-rose-400"
                  >
                    {t.ngo.whtRemoveRow}
                  </button>
                ) : null}
              </div>
            ))}
            <button
              type="button"
              onClick={() => setWhtRows((prev) => [...prev, emptyRow()])}
              className="rounded-full border border-zinc-300 px-3 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              + {t.ngo.whtAddRow}
            </button>
          </div>
        </Section>

        {/* Declarations */}
        <Section title={t.ngo.sectionDeclarationTitle}>
          <fieldset className="rounded-xl bg-amber-50 p-4 text-sm dark:bg-amber-950/40">
            <label className="flex items-start gap-2 text-amber-900 dark:text-amber-200">
              <input
                type="checkbox"
                className="mt-1"
                checked={exemptionAffirmed}
                onChange={(e) => setExemptionAffirmed(e.target.checked)}
              />
              <span>{t.ngo.exemptionDeclaration}</span>
            </label>
            <label className="mt-3 flex items-start gap-2 text-amber-900 dark:text-amber-200">
              <input
                type="checkbox"
                className="mt-1"
                checked={declarationAffirmed}
                onChange={(e) => setDeclarationAffirmed(e.target.checked)}
              />
              <span>{t.ngo.signatoryDeclaration}</span>
            </label>
          </fieldset>
        </Section>

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-full bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-40 sm:w-auto"
        >
          {busy ? t.ngo.submitting : t.ngo.submit}
        </button>
      </form>

      {error ? (
        <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          ⚠️ {error}
        </p>
      ) : null}

      {created ? (
        <section className="rounded-2xl border border-emerald-300 bg-emerald-50 p-5 dark:border-emerald-800 dark:bg-emerald-950/40">
          <h2 className="text-lg font-semibold">✅ {t.ngo.resultHeading}</h2>
          <p className="mt-2 text-sm">
            Filing ID <span className="font-mono">{created.id}</span> ·
            status <span className="font-mono">{created.audit_status}</span>
          </p>
          <Link
            href={`/ngo-filings/${created.id}`}
            className="mt-4 inline-flex items-center rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {t.ngo.viewFiling} →
          </Link>
        </section>
      ) : null}

      <footer className="pt-2 text-sm">
        <Link href="/chat" className="text-zinc-500 hover:underline">
          ← {t.dashboard.backToChat}
        </Link>
      </footer>
    </main>
  );
}

// --- reusable primitives ---------------------------------------------------

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
}

interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  helperId?: string;
  helper?: string;
  required?: boolean;
  type?: string;
}

function TextField(props: FieldProps) {
  return (
    <div>
      <label htmlFor={props.id} className="block text-xs text-zinc-500">
        {props.label}
      </label>
      <input
        id={props.id}
        type={props.type ?? "text"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        required={props.required}
        aria-describedby={props.helperId}
        className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-2 py-2 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
      />
      {props.helper ? (
        <p id={props.helperId} className="mt-1 text-[11px] text-zinc-500">
          {props.helper}
        </p>
      ) : null}
    </div>
  );
}

function NumberField(props: FieldProps & { min?: number; max?: number; step?: number }) {
  return (
    <div>
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
