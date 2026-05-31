# Next.js standalone (см. next.config.ts → output: "standalone")
# Сборка из корня репозитория: docker build -f web/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /repo/web
COPY web/package.json web/package-lock.json* ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /repo
COPY --from=deps /repo/web/node_modules ./web/node_modules
COPY web ./web
COPY scripts/generate-seo-landings.mjs ./scripts/
COPY data/seo-landings.json ./data/
WORKDIR /repo/web
COPY data/fuel_label_aliases.json src/lib/fuel_label_aliases.json
ENV NEXT_TELEMETRY_DISABLED=1
ARG WRA_API_INTERNAL=http://api:8080
ENV WRA_API_INTERNAL=$WRA_API_INTERNAL
# Inlined at `next build` into the client bundle. Пусто = браузер бьёт в /api на том же host (rewrites).
ARG NEXT_PUBLIC_API_BASE=
ARG NEXT_PUBLIC_SITE_URL=https://rideauto.ru
ARG NEXT_PUBLIC_SENTRY_DSN=
ARG NEXT_PUBLIC_FEATURE_VIRTUAL_LIST=
ARG NEXT_PUBLIC_FEATURE_HOME_TRUST=1
ARG WRA_ISR_WARM_CAR_REFS=
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_SENTRY_DSN=$NEXT_PUBLIC_SENTRY_DSN
ENV NEXT_PUBLIC_FEATURE_VIRTUAL_LIST=$NEXT_PUBLIC_FEATURE_VIRTUAL_LIST
ENV NEXT_PUBLIC_FEATURE_HOME_TRUST=$NEXT_PUBLIC_FEATURE_HOME_TRUST
ENV WRA_ISR_WARM_CAR_REFS=$WRA_ISR_WARM_CAR_REFS
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# SSR (getServerApiBase) читает это в рантайме; совпадает с build ARG по умолчанию. Compose может переопределить.
ENV WRA_API_INTERNAL=http://api:8080
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /repo/web/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /repo/web/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
