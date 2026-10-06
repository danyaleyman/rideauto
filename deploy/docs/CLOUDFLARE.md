# Cloudflare edge (RideAuto)

Runbook for prod edge in front of nginx/API. Fill the checklist after applying rules in the CF dashboard.

## Goals

- Cache static Next assets aggressively; carefully cache `/api/search` only when CDN headers allow.
- Rate-limit abusive clients at edge **and** rely on API `WRA_RATE_LIMIT_*` (Redis for multi-worker).
- Protect `/api/internal/*` and `/api/meili/outbox/process` (secret + preferably CF Access / IP allowlist).

## Recommended settings

1. **SSL/TLS:** Full (strict) to origin.
2. **Caching:**
   - Bypass or short TTL for HTML document routes.
   - Cache `_next/static/*` long TTL.
   - `/api/search`: respect `CDN-Cache-Control` / `Cache-Control` from [`cdn_cache.py`](../../backend/fastapi_app/middleware/cdn_cache.py); do not force-cache authenticated responses.
3. **Rate limiting (WAF custom rules):** e.g. 120 req/min per IP on `/api/*` (tune with `WRA_RATE_LIMIT_PUBLIC_PER_MINUTE`).
4. **Forwarded IP:** set `WRA_RATE_LIMIT_TRUST_FORWARDED_FOR=1` only when CF is the sole edge (see `deploy/env.rideauto.example`).
5. **Internal routes:** Block public access to `/api/internal/*` unless `X-WRA-Admin-Key` / `X-Admin-Key` present; prefer CF Access.

## Env on origin

```bash
WRA_RATE_LIMIT_PUBLIC_PER_MINUTE=60
WRA_RATE_LIMIT_TRUST_FORWARDED_FOR=1
WRA_REDIS_URL=redis://127.0.0.1:6379/0   # multi-worker
# rotate periodically:
# WRA_CACHE_INVALIDATE_SECRET=...
```

Nginx companion: `deploy/nginx/http-rate-limit-api.snippet.conf`.

## Prod verification checklist

- [ ] CF rules exported / screenshots attached (ops wiki or this file appendix).
- [ ] `curl -I https://rideauto.ru/api/search?...` shows expected CDN/cache headers.
- [ ] Burst → HTTP 429 from API and/or CF.
- [ ] `curl https://rideauto.ru/api/internal/cache/invalidate` without secret → 401/403.
- [ ] Admin key rotation recorded (date/operator).

## Sign-off

| Field | Value |
|-------|-------|
| Date | |
| Operator | |
| Zone | |
| Notes | |
