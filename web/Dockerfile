# Next.js standalone (см. next.config.ts → output: "standalone")
# Сборка из корня репозитория: docker build -f web/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ .
COPY frontend ./frontend-legacy
ENV NEXT_TELEMETRY_DISABLED=1
ENV WRA_FRONTEND_ROOT=/app/frontend-legacy
ARG WRA_API_INTERNAL=http://api:8080
ENV WRA_API_INTERNAL=$WRA_API_INTERNAL
# Inlined at `next build` into the client bundle — pass real prod URLs from compose/build, not only runtime env.
ARG NEXT_PUBLIC_API_BASE=http://127.0.0.1:8080
ARG NEXT_PUBLIC_SITE_URL=https://rideauto.ru
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
RUN node scripts/sync-legacy-assets.mjs
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
