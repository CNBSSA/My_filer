import Link from "next/link";

import { getMessages } from "@/lib/messages";

export default function Home() {
  const t = getMessages("en");
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-4 py-12 sm:gap-8 sm:px-6 sm:py-24">
      <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-200">
        Nigeria · 2026
      </span>
      <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
        {t.appName}
      </h1>
      <p className="text-lg text-zinc-600 dark:text-zinc-400 sm:text-xl">
        {t.tagline}
      </p>
      <div className="space-y-3 text-zinc-700 dark:text-zinc-300">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
          {t.aboutHeading}
        </h2>
        <p className="max-w-2xl leading-7">{t.aboutBody}</p>
      </div>
      <div className="mt-2 flex w-full flex-col gap-3 sm:mt-4 sm:w-auto sm:flex-row sm:flex-wrap">
        <Link
          href="/chat"
          className="inline-flex items-center justify-center rounded-full bg-zinc-900 px-6 py-3 text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white"
        >
          {t.startChat} →
        </Link>
        <Link
          href="/identity"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 px-6 py-3 text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
        >
          {t.identity.title} →
        </Link>
        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center rounded-full border border-zinc-300 px-6 py-3 text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
        >
          {t.dashboard.title} →
        </Link>
      </div>
    </main>
  );
}
