/**
 * Playwright config — **optional** deep a11y testing.
 *
 * The primary accessibility harness is `npm run test:a11y` (jsdom + axe-core,
 * zero browser dependency). Use the Playwright path when you want axe to
 * see real browser-computed styles + client-side JS — it catches things
 * jsdom can't, e.g. colour-contrast on dynamically-rendered content.
 *
 * One-time setup (in any environment with outbound network to Google's
 * Chrome-for-Testing CDN):
 *
 *     cd apps/web
 *     npm run test:a11y:browser:install        # downloads Chromium
 *
 * Then:
 *
 *     npm run test:a11y:browser
 *
 * The config boots `next start` via Playwright's webServer so you don't
 * need to pre-start it. Set A11Y_BASE_URL to point at an already-running
 * server if you prefer.
 */

import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.A11Y_PORT ?? "3460");
const BASE_URL =
  process.env.A11Y_BASE_URL ?? `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.A11Y_BASE_URL
    ? undefined
    : {
        command: `next start -p ${PORT} -H 127.0.0.1`,
        url: BASE_URL,
        timeout: 60_000,
        reuseExistingServer: !process.env.CI,
      },
});
