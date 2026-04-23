# Mai Filer Web — production Dockerfile.
#
# Three stages: `deps` installs node_modules with the lockfile for cache
# reuse, `builder` runs `next build` to emit the standalone output, and
# `runtime` copies only `.next/standalone/` + static assets. Final image
# is ~150 MB (node:22-alpine base) instead of ~1 GB of a dev install.
#
# `NEXT_PUBLIC_API_BASE` is baked in at build time (it's inlined into the
# client bundle). Railway / ECS pass it via build args; default points at
# localhost for local `docker build`.

# -----------------------------------------------------------------------------
# deps — lockfile-only install so caching survives source changes
# -----------------------------------------------------------------------------
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# -----------------------------------------------------------------------------
# builder — compile Next.js to standalone
# -----------------------------------------------------------------------------
FROM node:22-alpine AS builder

ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE=${NEXT_PUBLIC_API_BASE} \
    NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# -----------------------------------------------------------------------------
# runtime — minimal image with only what the standalone server needs
# -----------------------------------------------------------------------------
FROM node:22-alpine AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

# Next's standalone output contains its own vendored server + trimmed
# node_modules. `public/` and `.next/static/` are not included by standalone
# and must be copied explicitly.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# server.js is the standalone server Next emits. HOSTNAME + PORT are read
# from env (set above), so Railway's dynamic $PORT just works.
CMD ["node", "server.js"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+ (process.env.PORT||3000) +'/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
