import Link from "next/link";

import { getMessages } from "@/lib/messages";

export default function Home() {
  const t = getMessages("en");
  return (
    <main className="relative mx-auto flex min-h-screen max-w-4xl flex-col items-start justify-center gap-8 px-4 py-12 sm:px-6 sm:py-20">
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

      {/* Taxpayer type cards */}
      <div className="w-full">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-zinc-400">
          Who are you filing for?
        </h2>
        <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-3">

          {/* Individual */}
          <Link
            href="/chat"
            className="group flex flex-col gap-3 rounded-2xl border border-emerald-100 bg-white p-6 shadow-sm transition-all hover:border-emerald-300 hover:shadow-md"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-2xl">
              👤
            </div>
            <div>
              <p className="font-semibold text-zinc-900 group-hover:text-emerald-700">Individual</p>
              <p className="mt-1 text-sm text-zinc-500">PIT / PAYE return</p>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Salaried employees, self-employed persons, and sole traders. File your annual Personal Income Tax return.
            </p>
            <span className="mt-auto inline-flex items-center text-xs font-semibold text-emerald-600 group-hover:underline">
              Start filing →
            </span>
          </Link>

          {/* Corporate */}
          <Link
            href="/corporate"
            className="group flex flex-col gap-3 rounded-2xl border border-blue-100 bg-white p-6 shadow-sm transition-all hover:border-blue-300 hover:shadow-md"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-2xl">
              🏢
            </div>
            <div>
              <p className="font-semibold text-zinc-900 group-hover:text-blue-700">Company</p>
              <p className="mt-1 text-sm text-zinc-500">CIT return · CAC Part-A</p>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Limited liability companies (Ltd / Plc) registered with CAC. File your annual Company Income Tax return.
            </p>
            <span className="mt-auto inline-flex items-center text-xs font-semibold text-blue-600 group-hover:underline">
              Start filing →
            </span>
          </Link>

          {/* NGO */}
          <Link
            href="/ngo"
            className="group flex flex-col gap-3 rounded-2xl border border-violet-100 bg-white p-6 shadow-sm transition-all hover:border-violet-300 hover:shadow-md"
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-50 text-2xl">
              🏛️
            </div>
            <div>
              <p className="font-semibold text-zinc-900 group-hover:text-violet-700">NGO / Charity</p>
              <p className="mt-1 text-sm text-zinc-500">Exempt return · CAC Part-C</p>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Non-profit organisations, foundations, and charities registered under CAC Part-C. Annual exempt-status return.
            </p>
            <span className="mt-auto inline-flex items-center text-xs font-semibold text-violet-600 group-hover:underline">
              Start filing →
            </span>
          </Link>

        </div>
      </div>

      {/* Secondary links */}
      <div className="flex w-full flex-wrap gap-3">
        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-50 hover:border-zinc-400"
        >
          {t.dashboard.title} →
        </Link>
        <Link
          href="/identity"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 bg-white px-6 py-2.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-50 hover:border-zinc-400"
        >
          {t.identity.title} →
        </Link>
      </div>

      {/* Trust strip */}
      <p className="text-xs text-zinc-400">
        🔒 NIN encrypted at rest · NDPR compliant · Audit Shield on every return
      </p>
    </main>
  );
}
