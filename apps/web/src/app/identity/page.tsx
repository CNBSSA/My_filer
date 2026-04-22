"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import {
  LANGUAGE_CODES,
  LANGUAGE_LABELS,
  LanguageCode,
  getMessages,
} from "@/lib/messages";
import { IdentityVerificationResult, verifyIdentity } from "@/lib/api";

function nameMatchMessage(
  status: IdentityVerificationResult["name_match_status"],
  t: ReturnType<typeof getMessages>,
): string | null {
  switch (status) {
    case "strict":
      return t.identity.nameMatchStrict;
    case "fuzzy":
      return t.identity.nameMatchFuzzy;
    case "mismatch":
      return t.identity.nameMatchMismatch;
    default:
      return null;
  }
}

export default function IdentityPage() {
  const [language, setLanguage] = useState<LanguageCode>("en");
  const [nin, setNin] = useState("");
  const [declaredName, setDeclaredName] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IdentityVerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const t = useMemo(() => getMessages(language), [language]);

  const ninValid = /^\d{11}$/.test(nin);
  const canSubmit = ninValid && consent && !busy;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await verifyIdentity({
        nin,
        consent,
        declared_name: declaredName || undefined,
      });
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-zinc-500">Phase 5</p>
          <h1 className="mt-1 text-2xl font-semibold">{t.identity.title}</h1>
          <p className="text-sm text-zinc-500">{t.identity.subtitle}</p>
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

      <form
        onSubmit={submit}
        className="space-y-5 rounded-2xl border border-zinc-200 p-5 dark:border-zinc-800"
      >
        <div>
          <label className="block text-sm font-medium">
            {t.identity.ninLabel}
          </label>
          <input
            type="text"
            inputMode="numeric"
            pattern="\d{11}"
            maxLength={11}
            value={nin}
            onChange={(e) => setNin(e.target.value.replace(/\D/g, "").slice(0, 11))}
            disabled={busy}
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono tracking-widest focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="12345678901"
          />
          <p className="mt-1 text-xs text-zinc-500">{t.identity.ninHelper}</p>
        </div>

        <div>
          <label className="block text-sm font-medium">
            {t.identity.nameLabel}
          </label>
          <input
            type="text"
            value={declaredName}
            onChange={(e) => setDeclaredName(e.target.value)}
            disabled={busy}
            className="mt-1 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900"
          />
          <p className="mt-1 text-xs text-zinc-500">{t.identity.nameHelper}</p>
        </div>

        <fieldset className="rounded-xl bg-amber-50 p-4 text-sm dark:bg-amber-950/40">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
            {t.identity.consentTitle}
          </legend>
          <p className="text-amber-900 dark:text-amber-200">{t.identity.consentBody}</p>
          <label className="mt-3 flex items-start gap-2 text-amber-900 dark:text-amber-200">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              disabled={busy}
              className="mt-1"
            />
            <span className="font-medium">{t.identity.consentCheckbox}</span>
          </label>
        </fieldset>

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-full bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-40"
        >
          {busy ? t.identity.submitting : t.identity.submit}
        </button>
      </form>

      {error ? (
        <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          ⚠️ {error}
        </p>
      ) : null}

      {result ? (
        <section
          className={
            "rounded-2xl border p-5 " +
            (result.verified
              ? "border-emerald-300 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/40"
              : "border-rose-300 bg-rose-50 dark:border-rose-800 dark:bg-rose-950/40")
          }
        >
          <h2 className="text-lg font-semibold">
            {result.verified
              ? `✅ ${t.identity.resultVerified}`
              : `❌ ${t.identity.resultNotVerified}`}
          </h2>
          {result.verified ? (
            <dl className="mt-3 space-y-1 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-600 dark:text-zinc-300">Full name</dt>
                <dd>{result.full_name ?? "—"}</dd>
              </div>
              {result.state_of_origin ? (
                <div className="flex justify-between gap-4">
                  <dt className="text-zinc-600 dark:text-zinc-300">State of origin</dt>
                  <dd>{result.state_of_origin}</dd>
                </div>
              ) : null}
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-600 dark:text-zinc-300">Aggregator</dt>
                <dd className="font-mono text-xs">{result.aggregator}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-zinc-600 dark:text-zinc-300">Consent log</dt>
                <dd className="font-mono text-xs">{result.consent_log_id ?? "—"}</dd>
              </div>
            </dl>
          ) : null}
          {nameMatchMessage(result.name_match_status, t) ? (
            <p
              className={
                "mt-3 rounded-md px-3 py-2 text-sm " +
                (result.name_match_status === "mismatch"
                  ? "bg-rose-100 text-rose-900 dark:bg-rose-950/60 dark:text-rose-100"
                  : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-100")
              }
            >
              {nameMatchMessage(result.name_match_status, t)}
            </p>
          ) : null}
          {!result.verified && result.error ? (
            <p className="mt-3 text-sm text-rose-800 dark:text-rose-200">
              {result.error}
            </p>
          ) : null}
          <div className="mt-4">
            <Link
              href="/chat"
              className="inline-flex items-center rounded-full bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
            >
              {t.identity.backToChat} →
            </Link>
          </div>
        </section>
      ) : null}

      <footer className="pt-2 text-sm">
        <Link href="/chat" className="text-zinc-500 hover:underline">
          ← Back to chat
        </Link>
      </footer>
    </main>
  );
}
