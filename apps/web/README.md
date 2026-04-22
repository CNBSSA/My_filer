# `apps/web` — Mai Filer Frontend (placeholder)

Chat-first UI for Mai Filer. The full Next.js 15 + TypeScript + Tailwind
scaffold is deferred to Phase 1 (see `/docs/ROADMAP.md` task P0.16) so the
first commit can land without depending on network-level npm installs.

## When Phase 1 starts

```bash
cd apps/web
npx create-next-app@latest . --ts --tailwind --app --src-dir --eslint --no-import-alias
```

Then wire `/chat` to the FastAPI `/v1/chat/stream` SSE endpoint per
`/docs/ARCHITECTURE.md` §4.
