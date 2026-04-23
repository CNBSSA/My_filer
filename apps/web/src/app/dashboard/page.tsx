"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  AnomalyFinding,
  MidYearNudge,
  YearlyFact,
  getAnomalies,
  getFacts,
  getNudges,
} from "@/lib/api";
import {
  LANGUAGE_CODES,
  LANGUAGE_LABELS,
  LanguageCode,
  getMessages,
} from "@/lib/messages";

const CURRENT_YEAR = new Date().getUTCFullYear();
const CURRENT_MONTH = new Date().getUTCMonth() + 1;

const SEVERITY_STYLES: Record<"info" | "watch" | "alert", string> = {
  info: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
  watch:
    "bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200",
  alert: "bg-rose-100 text-rose-900 dark:bg-rose-950/60 dark:text-rose-200",
};

function SeverityPill({
  severity,
}: {
  severity: "info" | "watch" | "alert";
}) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}

function formatMoney(value: string): string {
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return `₦${n.toLocaleString("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function DashboardPage() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const [ninHash, setNinHash] = useState("");
  const [taxYear, setTaxYear] = useState<number>(CURRENT_YEAR);
  const [ytdGross, setYtdGross] = useState("0");
  const [month, setMonth] = useState(CURRENT_MONTH);

  const [facts, setFacts] = useState<YearlyFact[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyFinding[]>([]);
  const [nudges, setNudges] = useState<MidYearNudge[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const t = useMemo(() => getMessages(language), [language]);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [factResp, anomaliesResp, nudgesResp] = await Promise.all([
        getFacts({ nin_hash: ninHash || null, limit: 200 }),
        getAnomalies({ nin_hash: ninHash || null, current_year: taxYear }),
        getNudges({
          nin_hash: ninHash || null,
          current_year: taxYear,
          ytd_gross: ytdGross || "0",
          month,
        }),
      ]);
      setFacts(factResp.facts);
      setAnomalies(anomaliesResp.findings);
      setNudges(nudgesResp.nudges);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [ninHash, taxYear, ytdGross, month]);

  useEffect(() => {
    void load();
    // Only run once on mount; the user uses Refresh after filter edits.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 px-4 py-6 sm:py-10">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold sm:text-3xl">
            {t.dashboard.title}
          </h1>
          <p className="mt-1 text-sm text-zinc-500">{t.dashboard.subtitle}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-zinc-500">{t.chat.language}</span>
          <select
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

      <section className="rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800 sm:p-5">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label htmlFor="dashboard-nin" className="flex flex-col text-xs text-zinc-500">
            {t.dashboard.filtersNinLabel}
            <input
              id="dashboard-nin"
              type="text"
              value={ninHash}
              onChange={(e) => setNinHash(e.target.value)}
              disabled={busy}
              placeholder="sha256 hex"
              className="mt-1 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <label htmlFor="dashboard-year" className="flex flex-col text-xs text-zinc-500">
            {t.dashboard.filtersYearLabel}
            <input
              id="dashboard-year"
              type="number"
              value={taxYear}
              min={2025}
              max={2100}
              onChange={(e) => setTaxYear(Number(e.target.value))}
              disabled={busy}
              className="mt-1 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <label htmlFor="dashboard-ytd" className="flex flex-col text-xs text-zinc-500">
            {t.dashboard.filtersYtdLabel}
            <input
              id="dashboard-ytd"
              type="number"
              min={0}
              step={10000}
              value={ytdGross}
              onChange={(e) => setYtdGross(e.target.value)}
              disabled={busy}
              className="mt-1 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
          <label htmlFor="dashboard-month" className="flex flex-col text-xs text-zinc-500">
            {t.dashboard.filtersMonthLabel}
            <input
              id="dashboard-month"
              type="number"
              min={1}
              max={12}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              disabled={busy}
              className="mt-1 rounded-md border border-zinc-300 bg-white px-2 py-1 text-sm focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={() => void load()}
            disabled={busy}
            className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
          >
            {busy ? "…" : t.dashboard.refresh}
          </button>
        </div>
      </section>

      {error ? (
        <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          ⚠️ {error}
        </p>
      ) : null}

      <section className="rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800 sm:p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.dashboard.factsHeading}
        </h2>
        {facts.length === 0 ? (
          <p className="text-sm text-zinc-500">{t.dashboard.factsEmpty}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase tracking-wider text-zinc-500">
                <tr>
                  <th className="pb-2 pr-4">Year</th>
                  <th className="pb-2 pr-4">Fact</th>
                  <th className="pb-2 pr-4 text-right">Value</th>
                  <th className="pb-2 pr-4">Source</th>
                </tr>
              </thead>
              <tbody>
                {facts.map((f) => (
                  <tr
                    key={f.id}
                    className="border-t border-zinc-100 dark:border-zinc-800"
                  >
                    <td className="py-2 pr-4">{f.tax_year}</td>
                    <td className="py-2 pr-4 font-mono text-xs">{f.fact_type}</td>
                    <td className="py-2 pr-4 text-right">
                      {f.value_kind === "decimal" && f.unit === "NGN"
                        ? formatMoney(f.value)
                        : f.value}
                    </td>
                    <td className="py-2 pr-4 text-xs text-zinc-500">
                      {f.source}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800 sm:p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.dashboard.anomaliesHeading}
        </h2>
        {anomalies.length === 0 ? (
          <p className="text-sm text-zinc-500">{t.dashboard.anomaliesEmpty}</p>
        ) : (
          <ul className="space-y-2">
            {anomalies.map((a, i) => (
              <li
                key={`${a.fact_type}-${i}`}
                className="flex flex-col gap-1 rounded-lg border border-zinc-200 p-3 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800"
              >
                <div className="flex items-center gap-2">
                  <SeverityPill severity={a.severity} />
                  <span className="font-mono text-xs">{a.fact_type}</span>
                </div>
                <span className="text-sm text-zinc-700 dark:text-zinc-300">
                  {a.message}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-2xl border border-zinc-200 p-4 dark:border-zinc-800 sm:p-5">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.dashboard.nudgesHeading}
        </h2>
        {nudges.length === 0 ? (
          <p className="text-sm text-zinc-500">{t.dashboard.nudgesEmpty}</p>
        ) : (
          <ul className="space-y-2">
            {nudges.map((n) => (
              <li
                key={n.code}
                className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
              >
                <div className="mb-1 flex items-center gap-2">
                  <SeverityPill severity={n.severity} />
                  <span className="font-mono text-xs">{n.code}</span>
                </div>
                <p className="text-sm">{n.message}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="pt-2 text-sm">
        <Link href="/chat" className="text-zinc-500 hover:underline">
          ← {t.dashboard.backToChat}
        </Link>
      </footer>
    </main>
  );
}
