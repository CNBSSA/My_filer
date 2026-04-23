"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  CITResult,
  WHTResult,
  calcCit,
  calcWht,
  listWhtClasses,
} from "@/lib/api";
import { API_BASE } from "@/lib/api";
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

export default function SmePage() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const t = useMemo(() => getMessages(language), [language]);

  // CIT inputs
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

      {/* CIT */}
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
