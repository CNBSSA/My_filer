"use client";

import Link from "next/link";
import { useState } from "react";

import {
  CITReturn,
  CorporateCompanyType,
  CorporateExpenseKind,
  CorporateFilingRecord,
  createCorporateFiling,
} from "@/lib/api";

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

const EXPENSE_LABELS: Record<CorporateExpenseKind, string> = {
  cost_of_sales: "Cost of Sales",
  salaries_wages: "Salaries & Wages",
  rent: "Rent",
  utilities: "Utilities",
  depreciation: "Depreciation",
  professional_fees: "Professional Fees",
  marketing: "Marketing",
  interest: "Interest",
  other: "Other",
};

interface ExpenseRow {
  kind: CorporateExpenseKind;
  label: string;
  amount: string;
}

interface RevenueRow {
  label: string;
  amount: string;
}

function Field({
  label,
  helper,
  children,
}: {
  label: string;
  helper?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-zinc-700">{label}</label>
      {helper && <p className="text-xs text-zinc-400">{helper}</p>}
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100";

const selectCls =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100";

export default function CorporateIntakePage() {
  const thisYear = new Date().getUTCFullYear();

  // Identity
  const [rcNumber, setRcNumber] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [companyType, setCompanyType] = useState<CorporateCompanyType>("LTD");
  const [tin, setTin] = useState("");
  const [address, setAddress] = useState("");
  const [industry, setIndustry] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [officerName, setOfficerName] = useState("");
  const [officerNin, setOfficerNin] = useState("");

  // Period
  const [taxYear, setTaxYear] = useState(thisYear);
  const [periodStart, setPeriodStart] = useState(`${thisYear}-01-01`);
  const [periodEnd, setPeriodEnd] = useState(`${thisYear}-12-31`);

  // Financials
  const [revenues, setRevenues] = useState<RevenueRow[]>([
    { label: "Sales / Service revenue", amount: "0" },
  ]);
  const [expenses, setExpenses] = useState<ExpenseRow[]>([
    { kind: "cost_of_sales", label: "Cost of Sales", amount: "0" },
    { kind: "salaries_wages", label: "Salaries & Wages", amount: "0" },
  ]);
  const [declaredTurnover, setDeclaredTurnover] = useState("");
  const [declaredProfit, setDeclaredProfit] = useState("");
  const [whtSuffered, setWhtSuffered] = useState("0");
  const [advanceTax, setAdvanceTax] = useState("0");
  const [notes, setNotes] = useState("");
  const [declaration, setDeclaration] = useState(false);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<CorporateFilingRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  function addRevenue() {
    setRevenues([...revenues, { label: "", amount: "0" }]);
  }
  function removeRevenue(i: number) {
    setRevenues(revenues.filter((_, idx) => idx !== i));
  }
  function updateRevenue(i: number, field: keyof RevenueRow, value: string) {
    setRevenues(revenues.map((r, idx) => (idx === i ? { ...r, [field]: value } : r)));
  }

  function addExpense() {
    setExpenses([...expenses, { kind: "other", label: "Other", amount: "0" }]);
  }
  function removeExpense(i: number) {
    setExpenses(expenses.filter((_, idx) => idx !== i));
  }
  function updateExpense(i: number, field: keyof ExpenseRow, value: string) {
    if (field === "kind") {
      const kind = value as CorporateExpenseKind;
      setExpenses(
        expenses.map((e, idx) =>
          idx === i ? { ...e, kind, label: EXPENSE_LABELS[kind] } : e,
        ),
      );
    } else {
      setExpenses(expenses.map((e, idx) => (idx === i ? { ...e, [field]: value } : e)));
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!declaration) {
      setError("You must affirm the declaration before submitting.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: CITReturn = {
        tax_year: taxYear,
        period_start: periodStart,
        period_end: periodEnd,
        taxpayer: {
          rc_number: rcNumber,
          company_name: companyName,
          company_type: companyType,
          tin: tin || null,
          registered_address: address || null,
          industry: industry || null,
          email: email || null,
          phone: phone || null,
          primary_officer_name: officerName || null,
          primary_officer_nin: officerNin || null,
        },
        revenues: revenues.map((r) => ({ label: r.label, amount: r.amount })),
        expenses: expenses.map((e) => ({
          kind: e.kind,
          label: e.label,
          amount: e.amount,
        })),
        declared_turnover: declaredTurnover || null,
        declared_assessable_profit: declaredProfit || null,
        wht_already_suffered: whtSuffered,
        advance_tax_paid: advanceTax,
        declaration,
        notes: notes || null,
      };
      const filing = await createCorporateFiling(body);
      setResult(filing);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center">
          <div className="mb-2 text-3xl">✅</div>
          <h2 className="mb-1 text-xl font-bold text-emerald-800">Filing created</h2>
          <p className="mb-4 text-sm text-emerald-700">
            Corporate CIT return for <strong>{taxYear}</strong> has been saved.
          </p>
          <Link
            href={`/corporate-filings/${result.id}`}
            className="inline-flex items-center justify-center rounded-full bg-emerald-600 px-6 py-3 font-semibold text-white hover:bg-emerald-700"
          >
            Review, audit &amp; download pack →
          </Link>
          <div className="mt-4">
            <Link href="/" className="text-sm text-zinc-500 hover:underline">
              ← Back to home
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      {/* Header */}
      <div className="mb-8">
        <Link href="/" className="mb-4 inline-block text-sm text-zinc-500 hover:underline">
          ← Back
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-3xl">🏢</span>
          <div>
            <h1 className="text-2xl font-bold text-zinc-900">Corporate CIT Return</h1>
            <p className="text-sm text-zinc-500">
              Companies Incorporated Tax — Tax year {thisYear}
            </p>
          </div>
        </div>

        {/* Placeholder banner */}
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          ⚠️ <strong>Illustrative 2026 CIT rates.</strong> This pack is ready for manual
          NRS submission. Once NRS publishes confirmed 2026 bands, Mai Filer updates
          automatically.
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Company identity */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-emerald-600">
            Company Details
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="CAC RC Number" helper="Part-A registration number">
              <input
                className={inputCls}
                placeholder="RC-123456"
                value={rcNumber}
                onChange={(e) => setRcNumber(e.target.value)}
                required
              />
            </Field>
            <Field label="Company Type">
              <select
                className={selectCls}
                value={companyType}
                onChange={(e) => setCompanyType(e.target.value as CorporateCompanyType)}
              >
                {COMPANY_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </Field>
            <Field label="Registered Company Name" helper="As it appears on CAC certificate">
              <input
                className={inputCls}
                placeholder="Acme Nigeria Limited"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
              />
            </Field>
            <Field label="TIN (optional)">
              <input
                className={inputCls}
                placeholder="Tax Identification Number"
                value={tin}
                onChange={(e) => setTin(e.target.value)}
              />
            </Field>
            <Field label="Industry (optional)">
              <input
                className={inputCls}
                placeholder="e.g. Technology, Manufacturing"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
              />
            </Field>
            <Field label="Email (optional)">
              <input
                type="email"
                className={inputCls}
                placeholder="company@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Phone (optional)">
              <input
                className={inputCls}
                placeholder="+234 800 000 0000"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Registered Address (optional)">
                <input
                  className={inputCls}
                  placeholder="1 Broad Street, Lagos Island, Lagos"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                />
              </Field>
            </div>
          </div>
        </section>

        {/* Authorised officer */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-emerald-600">
            Authorised Officer
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name">
              <input
                className={inputCls}
                placeholder="Director / Company Secretary"
                value={officerName}
                onChange={(e) => setOfficerName(e.target.value)}
              />
            </Field>
            <Field label="NIN (optional)">
              <input
                className={inputCls}
                placeholder="11-digit NIN"
                maxLength={11}
                value={officerNin}
                onChange={(e) => setOfficerNin(e.target.value)}
              />
            </Field>
          </div>
        </section>

        {/* Period */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-emerald-600">
            Filing Period
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Tax Year">
              <input
                type="number"
                className={inputCls}
                value={taxYear}
                onChange={(e) => setTaxYear(Number(e.target.value))}
                required
              />
            </Field>
            <Field label="Period Start">
              <input
                type="date"
                className={inputCls}
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                required
              />
            </Field>
            <Field label="Period End">
              <input
                type="date"
                className={inputCls}
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                required
              />
            </Field>
          </div>
        </section>

        {/* Revenues */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-emerald-600">
              Revenue Lines
            </h2>
            <button
              type="button"
              onClick={addRevenue}
              className="rounded-full border border-emerald-300 px-3 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
            >
              + Add line
            </button>
          </div>
          <div className="space-y-3">
            {revenues.map((rev, i) => (
              <div key={i} className="flex gap-2">
                <input
                  className={`${inputCls} flex-1`}
                  placeholder="Revenue description"
                  value={rev.label}
                  onChange={(e) => updateRevenue(i, "label", e.target.value)}
                  required
                />
                <input
                  type="number"
                  className={`${inputCls} w-36`}
                  placeholder="Amount (₦)"
                  value={rev.amount}
                  onChange={(e) => updateRevenue(i, "amount", e.target.value)}
                  min="0"
                  required
                />
                {revenues.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeRevenue(i)}
                    className="rounded-lg px-2 text-zinc-400 hover:text-red-500"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Expenses */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-emerald-600">
              Allowable Expenses
            </h2>
            <button
              type="button"
              onClick={addExpense}
              className="rounded-full border border-emerald-300 px-3 py-1 text-xs text-emerald-700 hover:bg-emerald-50"
            >
              + Add expense
            </button>
          </div>
          <div className="space-y-3">
            {expenses.map((exp, i) => (
              <div key={i} className="flex gap-2">
                <select
                  className={`${selectCls} w-44`}
                  value={exp.kind}
                  onChange={(e) => updateExpense(i, "kind", e.target.value)}
                >
                  {EXPENSE_KINDS.map((k) => (
                    <option key={k} value={k}>{EXPENSE_LABELS[k]}</option>
                  ))}
                </select>
                <input
                  className={`${inputCls} flex-1`}
                  placeholder="Description"
                  value={exp.label}
                  onChange={(e) => updateExpense(i, "label", e.target.value)}
                />
                <input
                  type="number"
                  className={`${inputCls} w-36`}
                  placeholder="Amount (₦)"
                  value={exp.amount}
                  onChange={(e) => updateExpense(i, "amount", e.target.value)}
                  min="0"
                />
                {expenses.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeExpense(i)}
                    className="rounded-lg px-2 text-zinc-400 hover:text-red-500"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Adjustments */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-widest text-emerald-600">
            Adjustments &amp; Tax Credits
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Declared Turnover (optional)"
              helper="Override if different from revenue total"
            >
              <input
                type="number"
                className={inputCls}
                placeholder="₦"
                value={declaredTurnover}
                onChange={(e) => setDeclaredTurnover(e.target.value)}
                min="0"
              />
            </Field>
            <Field label="Declared Assessable Profit (optional)">
              <input
                type="number"
                className={inputCls}
                placeholder="₦"
                value={declaredProfit}
                onChange={(e) => setDeclaredProfit(e.target.value)}
              />
            </Field>
            <Field label="WHT Already Suffered (₦)">
              <input
                type="number"
                className={inputCls}
                value={whtSuffered}
                onChange={(e) => setWhtSuffered(e.target.value)}
                min="0"
              />
            </Field>
            <Field label="Advance Tax Paid (₦)">
              <input
                type="number"
                className={inputCls}
                value={advanceTax}
                onChange={(e) => setAdvanceTax(e.target.value)}
                min="0"
              />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Notes (optional)">
                <textarea
                  className={`${inputCls} resize-none`}
                  rows={3}
                  placeholder="Any additional notes for the return…"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </Field>
            </div>
          </div>
        </section>

        {/* Declaration */}
        <section className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-emerald-600">
            Declaration
          </h2>
          <label className="flex cursor-pointer gap-3">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-zinc-300 accent-emerald-600"
              checked={declaration}
              onChange={(e) => setDeclaration(e.target.checked)}
            />
            <span className="text-sm text-zinc-600">
              I, the authorised officer, affirm that this return is true and complete to
              the best of my knowledge and belief, and that the figures disclosed are
              derived from the company&apos;s books of account for the period stated.
            </span>
          </label>
        </section>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            ⚠️ {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || !declaration}
          className="w-full rounded-full bg-emerald-600 py-3 font-semibold text-white shadow-md transition hover:bg-emerald-700 disabled:opacity-50"
        >
          {submitting ? "Creating filing…" : "Create corporate filing →"}
        </button>
      </form>
    </main>
  );
}
