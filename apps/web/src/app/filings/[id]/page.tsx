"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";

import {
  AuditReport,
  AuditStatus,
  FilingRecord,
  buildFilingPack,
  filingPackDownloadUrl,
  getFiling,
  runAudit,
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

function Money({ value }: { value: string | undefined | null }) {
  if (value === undefined || value === null) return <>—</>;
  const n = Number(value);
  if (Number.isNaN(n)) return <>{value}</>;
  return <>₦{n.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</>;
}

export default function FilingReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [filing, setFiling] = useState<FilingRecord | null>(null);
  const [audit, setAudit] = useState<AuditReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const f = await getFiling(id);
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
      const result = await runAudit(id);
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
      const result = await buildFilingPack(id);
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
  const taxpayer = (ret.taxpayer ?? {}) as Record<string, string | null>;
  const computation = (ret.computation ?? {}) as Record<string, string>;
  const sources = (ret.income_sources ?? []) as Array<
    Record<string, string>
  >;
  const settlementPayable = ret.net_payable as string | null;

  const canBuildPack = filing.audit_status !== "red";

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">
            Filing · Tax Year {filing.tax_year}
          </p>
          <h1 className="mt-1 text-2xl font-semibold">
            {taxpayer.full_name ?? "Unnamed taxpayer"}
          </h1>
          <p className="text-sm text-zinc-500">ID {filing.id}</p>
        </div>
        <StatusPill status={filing.audit_status} />
      </header>

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
                No findings — Mai Filer is ready to prepare your pack.
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
            No audit has been run yet. Press <strong>Run audit</strong> to
            have Mai Filer review this return.
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
            title={
              canBuildPack
                ? "Audit must be green or yellow to generate the pack."
                : "Audit is red — fix findings first."
            }
            className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-40"
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
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">NIN</dt>
              <dd>{taxpayer.nin ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Email</dt>
              <dd>{taxpayer.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Address</dt>
              <dd className="text-right">{taxpayer.residential_address ?? "—"}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
            Computation
          </h2>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Annual income</dt>
              <dd>
                <Money value={computation.annual_income} />
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Total deductions</dt>
              <dd>
                <Money value={computation.total_deductions} />
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Chargeable income</dt>
              <dd>
                <Money value={computation.chargeable_income} />
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Total tax</dt>
              <dd className="font-semibold">
                <Money value={computation.total_tax} />
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-zinc-500">Net payable</dt>
              <dd>
                <Money value={settlementPayable} />
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          Income sources
        </h2>
        {sources.length === 0 ? (
          <p className="text-sm text-zinc-500">No income sources recorded.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="pb-2">Payer</th>
                <th className="pb-2">Kind</th>
                <th className="pb-2 text-right">Gross</th>
                <th className="pb-2 text-right">Withheld</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s, i) => (
                <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                  <td className="py-2">{s.payer_name}</td>
                  <td className="py-2">{s.kind}</td>
                  <td className="py-2 text-right">
                    <Money value={s.gross_amount} />
                  </td>
                  <td className="py-2 text-right">
                    <Money value={s.tax_withheld} />
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
              href={filingPackDownloadUrl(filing.id, "pdf")}
              target="_blank"
              rel="noopener"
              className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
            >
              Download PDF
            </a>
            <a
              href={filingPackDownloadUrl(filing.id, "json")}
              target="_blank"
              rel="noopener"
              className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              Download JSON
            </a>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">
            Generate the pack to unlock downloads. The PDF is NRS-portal-ready;
            the JSON is validator-friendly.
          </p>
        )}
      </section>

      <footer className="pt-2 text-sm">
        <Link href="/chat" className="text-zinc-500 hover:underline">
          ← Back to chat
        </Link>
      </footer>
    </main>
  );
}
