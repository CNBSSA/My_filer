/**
 * Accessibility harness (P10.3).
 *
 * Boots the production Next.js build on a local port, fetches the rendered
 * HTML for every listed route, loads it into jsdom, and runs axe-core with
 * WCAG 2.1 AA + WCAG 2.2 AA rule sets.
 *
 * Outputs one line per rule violation so CI grep is straightforward, exits
 * non-zero on any `serious` or `critical` violation. Lower-severity findings
 * are printed but do not fail the run — tune via env:
 *
 *   A11Y_FAIL_LEVEL = minor | moderate | serious | critical   (default: serious)
 *   A11Y_BASE_URL   = http://localhost:<port>                 (override server)
 *   A11Y_SKIP_SERVER = 1                                       (don't boot next)
 */

import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { once } from "node:events";
import { cpSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import type { AxeResults, Result } from "axe-core";
import { JSDOM } from "jsdom";

const localRequire = createRequire(import.meta.url);

type Impact = "minor" | "moderate" | "serious" | "critical";

const ROUTES: readonly string[] = [
  "/",
  "/chat",
  "/identity",
  "/dashboard",
  "/ngo",
  "/sme",
];

const SEVERITY_RANK: Record<Impact, number> = {
  minor: 1,
  moderate: 2,
  serious: 3,
  critical: 4,
};

const FAIL_LEVEL: Impact = (
  (process.env.A11Y_FAIL_LEVEL as Impact | undefined) ?? "serious"
);
const FAIL_RANK = SEVERITY_RANK[FAIL_LEVEL] ?? SEVERITY_RANK.serious;

async function portIsFree(port: number): Promise<boolean> {
  try {
    await fetch(`http://127.0.0.1:${port}/`, {
      signal: AbortSignal.timeout(500),
    });
    return false;
  } catch {
    return true;
  }
}

async function ensureServer(): Promise<{
  url: string;
  child: ChildProcessWithoutNullStreams | null;
}> {
  if (process.env.A11Y_BASE_URL) {
    return { url: process.env.A11Y_BASE_URL, child: null };
  }
  if (process.env.A11Y_SKIP_SERVER === "1") {
    return { url: "http://localhost:3000", child: null };
  }
  const port = process.env.A11Y_PORT ?? "3457";
  const portNum = Number(port);
  const url = `http://localhost:${port}`;

  if (!(await portIsFree(portNum))) {
    console.warn(
      `   port ${port} is busy — reuse the running server by setting ` +
        `A11Y_BASE_URL=${url} or pick a different A11Y_PORT.`,
    );
    return { url, child: null };
  }

  // `output: standalone` emits .next/standalone/server.js, which is the
  // same entrypoint our production Docker image runs. The standalone
  // output does NOT include public/ or .next/static/ — the Dockerfile
  // copies them in, and we mirror that here so the harness tests the
  // real production execution path instead of `next start`.
  const standaloneRoot = resolve(".next/standalone");
  if (existsSync("public")) {
    cpSync("public", resolve(standaloneRoot, "public"), { recursive: true });
  }
  if (existsSync(".next/static")) {
    cpSync(".next/static", resolve(standaloneRoot, ".next/static"), {
      recursive: true,
    });
  }

  console.log(`→ starting standalone server on ${url}`);
  const child = spawn("node", ["server.js"], {
    cwd: standaloneRoot,
    env: {
      ...process.env,
      NODE_ENV: "production",
      PORT: port,
      HOSTNAME: "127.0.0.1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (chunk) => {
    const line = chunk.toString().trim();
    if (line) console.log(`   [next] ${line}`);
  });
  child.stderr.on("data", (chunk) => {
    const line = chunk.toString().trim();
    if (line) console.error(`   [next:err] ${line}`);
  });

  // Poll for readiness.
  for (let attempt = 0; attempt < 60; attempt++) {
    try {
      const response = await fetch(url, { method: "GET" });
      if (response.ok || response.status === 404) break;
    } catch {
      // not ready yet
    }
    await sleep(500);
  }
  return { url, child };
}

async function runForRoute(
  baseUrl: string,
  route: string,
): Promise<{ route: string; results: AxeResults }> {
  const target = baseUrl.replace(/\/$/, "") + route;
  const response = await fetch(target, { redirect: "follow" });
  if (!response.ok) {
    throw new Error(`fetch ${target} -> ${response.status}`);
  }
  const html = await response.text();
  // Canvas is not implemented in jsdom; axe uses it for an icon-ligature
  // heuristic inside colour-contrast. Silence the warnings so the harness
  // output stays grep-friendly.
  const virtualConsole = new (await import("jsdom")).VirtualConsole();
  virtualConsole.on("jsdomError", (err: Error) => {
    if (err.message.includes("HTMLCanvasElement.prototype.getContext")) return;
    console.error(err);
  });
  const dom = new JSDOM(html, {
    url: target,
    pretendToBeVisual: true,
    virtualConsole,
  });

  // axe-core reads `window` + `document` at import time, so we set the
  // globals BEFORE we require it — then import fresh per run so it sees
  // the jsdom realm, not the Node globals.
  const g = globalThis as unknown as Record<string, unknown>;
  const originals: Record<string, unknown> = {};
  for (const key of [
    "window",
    "document",
    "Node",
    "HTMLElement",
    "Element",
    "navigator",
    "getComputedStyle",
  ] as const) {
    originals[key] = g[key];
    g[key] = (dom.window as unknown as Record<string, unknown>)[key];
  }

  let results: AxeResults;
  try {
    const cacheKey = localRequire.resolve("axe-core");
    // Force a fresh evaluation so axe's internal globals point at jsdom.
    delete localRequire.cache[cacheKey];
    const mod = localRequire("axe-core") as typeof import("axe-core");
    results = await mod.run(dom.window.document, {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
      },
      resultTypes: ["violations"],
    });
  } finally {
    for (const key of Object.keys(originals)) {
      g[key] = originals[key];
    }
    dom.window.close();
  }
  return { route, results };
}

function printViolations(route: string, violations: Result[]): void {
  if (violations.length === 0) {
    console.log(`✓ ${route} — no violations`);
    return;
  }
  console.log(`⚠ ${route} — ${violations.length} violation(s)`);
  for (const v of violations) {
    const impact = (v.impact ?? "minor") as Impact;
    console.log(
      `   [${impact.toUpperCase()}] ${v.id}: ${v.help}\n     ${v.helpUrl}`,
    );
    for (const node of v.nodes.slice(0, 5)) {
      console.log(`     target: ${node.target.join(" > ")}`);
      if (node.failureSummary) {
        console.log(
          `     hint:   ${node.failureSummary.replace(/\n/g, " ")}`,
        );
      }
    }
    if (v.nodes.length > 5) {
      console.log(`     … and ${v.nodes.length - 5} more node(s)`);
    }
  }
}

async function main(): Promise<number> {
  const { url, child } = await ensureServer();
  let exit = 0;
  try {
    for (const route of ROUTES) {
      try {
        const { results } = await runForRoute(url, route);
        printViolations(route, results.violations);
        for (const v of results.violations) {
          const impact = (v.impact ?? "minor") as Impact;
          if ((SEVERITY_RANK[impact] ?? 1) >= FAIL_RANK) {
            exit = 1;
          }
        }
      } catch (err) {
        console.error(`✗ ${route} — ${(err as Error).message}`);
        exit = 1;
      }
    }
  } finally {
    if (child) {
      child.kill("SIGTERM");
      try {
        await Promise.race([once(child, "exit"), sleep(3000)]);
      } catch {
        /* ignore */
      }
    }
  }
  if (exit === 0) {
    console.log(
      `\naxe: no violations at level ${FAIL_LEVEL.toUpperCase()} or above`,
    );
  } else {
    console.log(
      `\naxe: failing the run — at least one violation at level >= ${FAIL_LEVEL.toUpperCase()}`,
    );
  }
  return exit;
}

main().then(
  (code) => process.exit(code),
  (err) => {
    console.error(err);
    process.exit(2);
  },
);
