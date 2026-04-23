/**
 * Playwright + axe accessibility tests.
 *
 * Run locally with `npm run test:a11y:browser` after installing Chromium
 * via `npm run test:a11y:browser:install`. These tests use a real browser
 * and therefore cover checks the jsdom harness (`npm run test:a11y`) can't,
 * notably colour-contrast and dynamic-content issues.
 *
 * Scope: WCAG 2.0 / 2.1 / 2.2 Level AA. Violations of `serious` or
 * `critical` impact fail the test; lower-severity findings are reported.
 */

import { AxeBuilder } from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const ROUTES = ["/", "/chat", "/identity", "/dashboard", "/ngo", "/sme"] as const;

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function scan(page: Page, route: string) {
  await page.goto(route, { waitUntil: "networkidle" });
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  if (serious.length) {
    console.error(
      `✗ ${route} — ${serious.length} serious / critical violation(s):\n` +
        serious
          .map(
            (v) =>
              `  [${v.impact?.toUpperCase()}] ${v.id}: ${v.help}\n    ${v.helpUrl}`,
          )
          .join("\n"),
    );
  }
  return { results, serious };
}

for (const route of ROUTES) {
  test(`a11y — ${route}`, async ({ page }) => {
    const { serious } = await scan(page, route);
    expect(serious).toHaveLength(0);
  });
}
