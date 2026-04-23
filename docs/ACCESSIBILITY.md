# Accessibility — Mai Filer

> Mai Filer targets **WCAG 2.2 Level AA** (which includes 2.0 / 2.1 AA).
> The `test:a11y` script is the regression gate; no merge should land a
> **serious** or **critical** violation without an explicit owner
> waiver tracked in `docs/PENDING_WORK.md`.

## Two harnesses

| Harness | How to run | Depends on | What it catches |
|---|---|---|---|
| **jsdom + axe-core** (primary) | `npm run test:a11y` inside `apps/web` | `axe-core`, `jsdom`, `tsx` (already in devDeps) | Markup-level WCAG issues: labels, landmarks, alt text, aria-*, heading order, button / link names |
| **Playwright + axe-core** (deep) | `npm run test:a11y:browser:install` (once) → `npm run test:a11y:browser` | Chromium via Playwright | Everything the jsdom harness catches, **plus** computed-style issues like colour-contrast on dynamic content |

Both run against a production `next start` build. The primary harness
boots its own Next server on port `3457`; set `A11Y_BASE_URL` to point
at an already-running dev / staging environment instead.

## Severity policy

`axe-core` classifies each finding as `minor`, `moderate`, `serious`,
or `critical`. The harness exits non-zero when any finding at the
`A11Y_FAIL_LEVEL` or above is present. Default is `serious`.

```bash
# Stricter — any finding fails the run:
A11Y_FAIL_LEVEL=minor npm run test:a11y

# Looser — only critical fails (not recommended):
A11Y_FAIL_LEVEL=critical npm run test:a11y
```

## Adding a new route

1. Create the page under `apps/web/src/app/<route>/page.tsx`.
2. Add the path to the `ROUTES` tuple in `scripts/a11y.ts`
   **and** `tests/a11y.spec.ts`.
3. Run `npm run test:a11y`. If it fails, fix the route and commit both
   the page and the harness change in the same commit.

## Common fixes

| Rule | Symptom | Fix |
|---|---|---|
| `label` | `Form elements must have labels` | Pair `<label htmlFor="foo">` with `<input id="foo">`, or wrap the input inside `<label>`. Placeholder text does NOT satisfy this rule. |
| `button-name` | `Buttons must have discernible text` | Add visible text, or `aria-label`. For icon-only buttons (e.g. `📎`), wrap the icon in `<span aria-hidden="true">` and provide `aria-label` on the button. |
| `color-contrast` | `Elements must have sufficient color contrast` | Run the **Playwright** harness — jsdom can't verify this. Tailwind `text-zinc-500` on `bg-white` passes; `text-zinc-400` may not. |
| `heading-order` | `Heading levels should only increase by one` | Page should start at `<h1>`; nested sections use `<h2>` and below in order. |
| `html-has-lang` | `<html>` has no `lang` attribute | Next.js sets `<html lang="en">` by default in `app/layout.tsx`. If you localize the root document, update `<Html lang={…}>` accordingly. |
| `landmark-one-main` | `Page must have exactly one main landmark` | Every page renders `<main>` as the top-level wrapper. |

## CI integration

Wire the primary harness into whatever CI runs the Python suite (GitHub
Actions / GitLab / Buildkite — none is currently live). Minimal job:

```yaml
- name: Install web deps
  run: cd apps/web && npm ci
- name: Build web
  run: cd apps/web && npm run build
- name: Accessibility gate
  run: cd apps/web && npm run test:a11y
```

The Playwright deep-test job is a second optional step, only needed
when you want browser-level coverage on every PR:

```yaml
- name: Install Chromium
  run: cd apps/web && npm run test:a11y:browser:install
- name: Browser a11y
  run: cd apps/web && npm run test:a11y:browser
```

## Why two harnesses

The jsdom path is dependency-light (~10 MB) and works anywhere with a
Node install — including sandboxed CI runners that can't download
Chrome binaries. It covers ~80% of what `axe-core` normally reports.

The Playwright path downloads Chromium (~150 MB) and reproduces real
browser rendering, catching the remaining ~20% (mostly colour-contrast
on pages with CSS-in-JS or dynamically-computed values).

Use the jsdom path for every CI run; use the Playwright path locally
before a release cut or when introducing significant styling changes.

## Current baseline

As of the P10.3 commit: **0 serious / critical violations** across
`/`, `/chat`, `/identity`, `/dashboard`. Add the `/ngo` and `/sme`
routes to the `ROUTES` list when their Phase 11 / Phase 9 intake
pages land.
