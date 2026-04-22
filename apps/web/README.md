# Mai Filer — Web App

Chat-first Next.js 16 + TypeScript + Tailwind UI for Mai Filer. Talks to the
FastAPI backend at `../api/`.

## Run locally

1. Start the backend (`apps/api/`):
   ```bash
   cd apps/api
   uv sync              # or: pip install -e ".[dev]"
   alembic upgrade head
   uvicorn app.main:app --reload
   ```
2. Start the web app in another terminal:
   ```bash
   cd apps/web
   npm install
   npm run dev         # http://localhost:3000
   ```

The API URL is configurable via `NEXT_PUBLIC_API_BASE`
(default `http://localhost:8000`).

## Structure

- `src/app/page.tsx` — landing hero.
- `src/app/chat/page.tsx` — chat with language selector and SSE stream.
- `src/lib/messages.ts` — message catalog loader (en, ha, yo, ig, pcm).
- `src/lib/api.ts` — `streamChat()` SSE client for `POST /v1/chat/stream`.
- `messages/{code}.json` — UI strings per language (ADR-0004).
