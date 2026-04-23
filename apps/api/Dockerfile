# Mai Filer API — production Dockerfile.
#
# Multi-stage build: the "builder" image installs Python deps into a venv,
# the "runtime" image copies only the venv + app source. Keeps the final
# image small and avoids leaking build tools into production.
#
# Used by Railway (builder=DOCKERFILE in railway.json) and slots directly
# into AWS ECR / ECS when the production cutover happens.

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

# libpq + build-essential are needed to build psycopg from source on some
# slim tags. They never ship to the runtime stage.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

WORKDIR /build
COPY pyproject.toml ./
# Pre-install deps off the pyproject before copying the full tree so the
# Docker layer cache survives code-only changes.
RUN pip install --upgrade pip \
 && pip install -e .

# Now pull the source in and reinstall (fast, just registers the package).
COPY . .
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

# libpq for the Postgres driver at runtime; curl for the container
# healthcheck below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system mai --gid 1000 \
 && useradd --system --uid 1000 --gid mai --home-dir /app mai

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=mai:mai . /app

USER mai

# Railway supplies $PORT dynamically; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# Alembic runs in preDeployCommand (see railway.json) so the migration step
# doesn't happen on every container restart. The startCommand stays minimal
# and fast-to-restart.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD curl -fsSL "http://127.0.0.1:${PORT:-8000}/health" || exit 1
