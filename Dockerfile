# Root-level Dockerfile for the API service on Railway.
#
# Why this exists at the repo root (and not only at apps/api/Dockerfile):
#   Railway's single-service monorepo setup scans the repo root for a
#   Dockerfile. If the service's "Root Directory" isn't set in the Railway
#   dashboard, it falls back to Railpack auto-detect, which fails with
#   "Error creating build plan with Railpack" on monorepos.
#
#   Shipping this file at root means the build succeeds with zero
#   dashboard clicks. For a second service that deploys the web app,
#   create a new Railway service and set its Root Directory to `apps/web`
#   (it will then use apps/web/Dockerfile).
#
# Build context: repo root. All COPY paths are qualified with apps/api/.

# -----------------------------------------------------------------------------
# Builder
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV" \
 && pip install --upgrade pip

WORKDIR /build

# Copy the full API tree first — hatchling (build-backend) needs the
# `app/` package dir present when `pip install -e .` runs, so we can't
# split the pyproject copy from the source copy.
COPY apps/api/ ./

RUN pip install -e .

# -----------------------------------------------------------------------------
# Runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    APP_ENV=production

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system mai --gid 1000 \
 && useradd --system --uid 1000 --gid mai --home-dir /app mai

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --from=builder --chown=mai:mai /build /app

USER mai

ENV PORT=8000
EXPOSE 8000

# Alembic runs in preDeployCommand (see railway.json) so the migration
# step doesn't happen on every container restart.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsSL "http://127.0.0.1:${PORT:-8000}/health" || exit 1
