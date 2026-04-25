"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  AuditReport,
  AuditStatus,
  CorporateFilingRecord,
  auditCorporateFiling,
  buildCorporatePack,
  corporatePackDownloadUrl,
  getCorporateFiling,
} from "@/lib/api";

const STATUS_STYLES: Record<AuditStatus, string> = {
  pending: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  yellow: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  red: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200",
};

function StatusPill({ status }: { status: AuditStatus }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

function Money({ value }: { value: unknown }) {
  if (value === undefined || value === null || value === "") return <>—</>;
  const n = Number(value);
  if (Number.isNaN(n)) return <>{String(value)}</>;
  return (
    <>₦{n.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</>
  );
}

export default function CorporateFilingReviewPage({ id }: { id: string }) {
  const [filing, setFiling] = useState<CorporateFilingRecord | null>(null);
  const [audit, setAudit] = useState<AuditReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const f = await getCorporateFiling(id);
      setFiling(f);
      setAudit(f.audit);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const doAudit = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await auditCorporateFiling(id);
      setFiling(result.filing);
      setAudit(result.audit);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [busy, id]);

  const doBuildPack = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await buildCorporatePack(id);
      setFiling(result.filing);
      setAudit(result.filing.audit);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [busy, id]);

  if (!filing) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        {error ? (
          <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
            {error}
          </p>
        ) : (
          <p className="text-sm text-zinc-500">Loading filing…</p>
        )}
      </main>
    );
  }

  const ret = filing.return as Record<string, unknown>;
  const tp = (ret.taxpayer ?? {}) as Record<string, unknown>;
  const revenues = (ret.revenues ?? []) as Array<Record<string, unknown>>;
  const expenses = (ret.expenses ?? []) as Array<Record<string, unknown>>;
  const computation = (ret.computation ?? {}) as Record<string, unknown>;
  const totalRevenue = ret.total_revenue as string | null;
  const totalExpenses = ret.total_expenses as string | null;
  const netPayable = ret.net_payable as string | null;

  const canBuildPack = filing.audit_status !== "red";

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            CIT filing · Tax year {filing.tax_year}
          </p>
          <h1 className="mt-1 text-2xl font-semibold">
            {(tp.company_name as string) ?? "Unnamed company"}
          </h1>
          <p className="text-sm text-zinc-500">ID {filing.id}</p>
        </div>
        <StatusPill status={filing.audit_status} />
      </header>

      <aside
        role="note"
        className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
      >
        ⚠️ CIT bands are still illustrative (placeholder). The computed
        liability will not be accurate until the owner replaces the
        statutory tables with the confirmed 2026 schedule.
      </aside>

      {error ? (
        <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          ⚠️ {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Audit Shield
        </h2>
        {audit ? (
          <>
            <p className="mb-3 text-sm">
              Latest status: <StatusPill status={audit.status} />
            </p>
            {audit.findings.length === 0 ? (
              <p className="text-sm text-emerald-700 dark:text-emerald-300">
                No findings — Mai Filer is ready to prepare your CIT pack.
              </p>
            ) : (
              <ul className="space-y-2">
                {audit.findings.map((f, i) => (
                  <li
                    key={`${f.code}-${i}`}
                    className={`rounded-lg border p-3 text-sm ${
                      f.severity === "error"
                        ? "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
                        : f.severity === "warn"
                        ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
                        : "border-zinc-300 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
                    }`}
                  >
                    <div className="font-mono text-xs opacity-70">
                      {f.severity.toUpperCase()} · {f.code}
                      {f.field_path ? ` · ${f.field_path}` : ""}
                    </div>
                    <div>{f.message}</div>
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <p className="text-sm text-zinc-500">
            No audit has been run yet. Press <strong>Run audit</strong>.
          </p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void doAudit()}
            disabled={busy}
            className="rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-medium hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
          >
            {busy ? "Working…" : "Run audit"}
          </button>
          <button
            type="button"
            onClick={() => void doBuildPack()}
            disabled={busy || !canBuildPack}
            className="rounded-full bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-40"
          >
            {busy ? "Working…" : "Prepare pack"}
          </button>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
            Taxpayer
          </h2>
          <dl className="space-y-1 text-sm">
            <Row label="RC number" value={String(tp.rc_number ?? "—")} />
            <Row label="Company type" value={String(tp.company_type ?? "—")} />
            <Row label="TIN" value={String(tp.tin ?? "—")} />
            <Row label="Industry" value={String(tp.industry ?? "—")} />
            <Row label="Email" value={String(tp.email ?? "—")} />
            <Row label="Phone" value={String(tp.phone ?? "—")} />
            <Row label="Address" value={String(tp.registered_address ?? "—")} />
            <Row
              label="Primary officer"
              value={String(tp.primary_officer_name ?? "—")}
            />
          </dl>
        </div>

        <div className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
            Summary
          </h2>
          <dl className="space-y-1 text-sm">
            <Row label="Total revenue" value={<Money value={totalRevenue} />} />
            <Row label="Total expenses" value={<Money value={totalExpenses} />} />
            <Row label="Tier" value={String(computation.tier ?? "—")} />
            <Row
              label="CIT amount"
              value={<Money value={computation.cit_amount} />}
            />
            <Row
              label="Tertiary tax"
              value={<Money value={computation.tertiary_amount} />}
            />
            <Row
              label="Net payable"
              value={
                <strong>
                  <Money value={netPayable} />
                </strong>
              }
            />
          </dl>
        </div>
      </section>

      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Revenues
        </h2>
        {revenues.length === 0 ? (
          <p className="text-sm text-zinc-500">No revenue lines recorded.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="pb-2">Label</th>
                <th className="pb-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {revenues.map((r, i) => (
                <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="py-2">{String(r.label)}</td>
                  <td className="py-2 text-right">
                    <Money value={r.amount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Expenses
        </h2>
        {expenses.length === 0 ? (
          <p className="text-sm text-zinc-500">No expense lines recorded.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="pb-2">Kind</th>
                <th className="pb-2">Label</th>
                <th className="pb-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {expenses.map((e, i) => (
                <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="py-2">{String(e.kind).replace(/_/g, " ")}</td>
                  <td className="py-2">{String(e.label)}</td>
                  <td className="py-2 text-right">
                    <Money value={e.amount} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Download
        </h2>
        {filing.pack_ready ? (
          <div className="flex flex-wrap gap-2">
            <a
              href={corporatePackDownloadUrl(filing.id, "pdf")}
              target="_blank"
              rel="noopener"
              className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
            >
              Download PDF
            </a>
            <a
              href={corporatePackDownloadUrl(filing.id, "json")}
              target="_blank"
              rel="noopener"
              className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              Download JSON
            </a>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">
            Generate the pack to unlock downloads.
          </p>
        )}
      </section>

      <footer className="pt-2 text-sm">
        <Link href="/sme" className="text-zinc-500 hover:underline">
          ← Back to SME / corporate home
        </Link>
      </footer>
    </main>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}
