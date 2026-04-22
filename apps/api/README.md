# `apps/api` — Mai Filer Backend

FastAPI service. Hosts Mai Filer (the Claude-orchestrated agent), the tax
calculator services, document intelligence, identity verification, filing-pack
generation, and the NRS gateway.

See `/docs/ARCHITECTURE.md` at the repo root for the full service map.

## Run locally

```bash
uv sync                          # or: pip install -e ".[dev]"
uvicorn app.main:app --reload    # http://localhost:8000
```

Health check: `GET http://localhost:8000/health`
