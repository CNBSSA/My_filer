import Link from "next/link";

import { getMessages } from "@/lib/messages";

export default function Home() {
  const t = getMessages("en");
  return (
    <main className="relative mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-4 py-12 sm:gap-8 sm:px-6 sm:py-24">
      {/* Subtle green glow behind the hero */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-32 h-[500px] w-[500px] rounded-full opacity-20"
        style={{ background: "radial-gradient(circle, #059669 0%, transparent 70%)" }}
      />

      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
        Nigeria · 2026
      </span>

      <div className="space-y-3">
        <h1 className="text-5xl font-bold leading-tight tracking-tight text-zinc-900 sm:text-6xl">
          <span className="text-emerald-600">Mai</span>{" "}
          <span>Filer</span>
        </h1>
        <p className="text-xl text-zinc-500 sm:text-2xl">{t.tagline}</p>
      </div>

      <div className="rounded-2xl border border-zinc-100 bg-zinc-50 p-5 shadow-sm">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-600">
          {t.aboutHeading}
        </h2>
        <p className="max-w-2xl leading-7 text-zinc-600">{t.aboutBody}</p>
      </div>

      <div className="mt-2 flex w-full flex-col gap-3 sm:mt-4 sm:w-auto sm:flex-row sm:flex-wrap">
        {/* Primary CTA */}
        <Link
          href="/chat"
          className="inline-flex items-center justify-center rounded-full bg-emerald-600 px-7 py-3 font-semibold text-white shadow-md transition-all hover:bg-emerald-700 hover:shadow-lg active:scale-95"
        >
          {t.startChat} →
        </Link>

        <Link
          href="/identity"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-3 text-zinc-700 transition-colors hover:bg-zinc-50 hover:border-zinc-400"
        >
          {t.identity.title} →
        </Link>
        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-3 text-zinc-700 transition-colors hover:bg-zinc-50 hover:border-zinc-400"
        >
          {t.dashboard.title} →
        </Link>
        <Link
          href="/ngo"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-3 text-zinc-700 transition-colors hover:bg-zinc-50 hover:border-zinc-400"
        >
          {t.ngo.title} →
        </Link>
        <Link
          href="/sme"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-3 text-zinc-700 transition-colors hover:bg-zinc-50 hover:border-zinc-400"
        >
          {t.sme.title} →
        </Link>
      </div>

      {/* Trust strip */}
      <p className="text-xs text-zinc-400">
        🔒 NIN encrypted at rest · NDPR compliant · Audit Shield on every return
      </p>
    </main>
  );
}
