# Mai Filer — Web App

**Memory anchor lives at the repo root**: see `../../CLAUDE.md` for the north
star, locked ten roles, stack, decisions (ADR-0001..0004), and compliance
guardrails. Anything in this directory must serve that vision.

This app is the chat-first UI for Mai Filer. It talks to the FastAPI backend
at `apps/api/` via:

- `GET /v1/languages` — supported language list for the selector
- `POST /v1/chat` — single-turn (non-streaming)
- `POST /v1/chat/stream` — SSE stream (`start` → `delta*` → `done`)

UI strings are held in `messages/{en,ha,yo,ig,pcm}.json` and the chosen
language is sent to the backend on every chat call (ADR-0004).
