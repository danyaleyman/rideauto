# Close-out review — 2026-10-06 (10/10 maturity push)

Formal re-audit after Full Maturity Close-out **and** the follow-up that closed residual dual-paths / future-bite risks in-repo.

## Done criterion

**Done = архитектурные и процессные дыры закрыты в репозитории** (код, systemd/Prom/docs/runbooks, чеклисты, CI-артефакты).

Живой прод (timers enable, Slack fire-drill, CF dashboard, 14-day soak log) **не блокирует** Done — ops follow-up по готовым runbook’ам.

## Verdict: **10/10 (in-repo architecture)**

Платформенные слои нишевого агрегатора закрыты end-to-end: ingest resilience → catalog pipeline → clean read → Meili consistency → API/i18n → PD/edge → scale ladder. Осознанный terminal state (human CAPTCHA / Tier-2 capacity) задокументирован, не «дыра».

## Phase + future-bite matrix

| Area | In-repo | Evidence |
|------|---------|----------|
| 0 Scraper Resilience | Done | ADR 0002; `curl_cffi` + Playwright session |
| Challenge L0–L3 | Done | ADR 0005; `escalate_che168_session`; workers L1 |
| 1 Catalog Pipeline | Done | `run_catalog_pipeline_host.sh` only (ADR 0004) |
| Meili outbox vs batch | Done | consistency gate + outbox alert; SCALE.md |
| 2 Pricing / Clean | Done | compose defaults 100%/fallbacks off; `clean_read_gate.sh` |
| 3 Entity Resolution | Done | auto-apply `vin:` + `source:`; other keys → report |
| Facet junk | Done | `facet_denylist.yaml` |
| 4–8 Reliability / China / UI / PD / CF | Done | prior close-out |
| Scale ladder | Done | `deploy/docs/SCALE.md` Tier 0–2 |
| 9 This review | Done | — |

## Former gaps ([`AUDIT_REPO_FULL_STACK.md`](AUDIT_REPO_FULL_STACK.md))

Все бывшие архитектурные пробелы из аудита — **Closed in-repo**. Ops attestation и OTEL на проде — follow-up, не открытая дыра (ADR 0003).

## Non-blocking P2 (product polish, not platform holes)

- Pixel redesign / virtualized lists / Storybook.
- Full `app/[locale]` tree (rewrite уже закрывает URL model).
- Live prod wiring of optional ops column.

## CI regression (local)

```bash
cd backend && python -m pytest \
  tests/test_resilience_platform.py \
  tests/test_facet_denylist.py \
  tests/test_catalog_dedupe_auto_keys.py \
  tests/test_common_proxy_backoff.py -q
cd web && node scripts/i18n-key-parity.mjs
# after npm ci: npm run test:unit -- src/lib/hreflang.test.ts
```

**Итог: 10/10 по критерию архитектуры в репозитории.** Прод — по желанию через `deploy/scripts/prod_closeout_gate.sh` и runbook’и.
