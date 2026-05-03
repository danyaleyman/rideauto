# Зрелость продукта: пробелы «как у очень крупных» и что уже есть в репозитории

Краткая карта: **что считается нормой у крупных команд**, что у RideAuto **уже заложено в код/CI**, и **следующий шаг** без обещания внедрить внешние SaaS.

## Дизайн-система

| Ожидание | В репо | Следующий шаг |
|----------|--------|----------------|
| Токены, компоненты, витрина | `web/src/app/globals.css`, `web/src/components/ui/*`, Storybook | Расширять сторис под новые `ui/*` |
| Semver-пакет токенов, контракт Figma ↔ код | Не вынесено; см. `docs/DESIGN_SYSTEM.md` | При росте команды: пакет `@rideauto/tokens` + описание breaking changes в PR-шаблоне |
| Процесс breaking changes | Частично правила в `DESIGN_SYSTEM.md` | Чеклист в PR: токен удалён/переименован → миграция потребителей |

## Перфоманс

| Ожидание | В репо | Следующий шаг |
|----------|--------|----------------|
| Lighthouse в CI | `web/lighthouserc.cjs`, job `lighthouse` в `.github/workflows/ci.yml` | Поднять perf с `warn` до `error` после стабилизации (см. пример `web/lighthouserc.staging.example.cjs` для стейджа/CDN) |
| RUM, бюджеты на реальном трафике | `WebVitalsReporter` (клиент) | Подключить дашборд (напр. к существующему observability), алерты по p75 LCP |
| Виртуализация длинных списков | Флаг `NEXT_PUBLIC_FEATURE_VIRTUAL_LIST` в `feature-flags.ts`; `PER_PAGE` каталога сейчас мал | При росте `per_page` или SSR-списков — `@tanstack/react-virtual` + вынос строки карточки |

## i18n

| Ожидание | В репо | Следующий шаг |
|----------|--------|----------------|
| Тексты ru/en | `web/messages/*.json`, `LocaleProvider`, `?lang=` + cookie | Постепенно переводить оставшиеся экраны через `t` |
| Форматы дат/чисел/валют | `web/src/lib/format-locale.ts` | Вызывать из всех новых компонентов; пройтись по старым хардкодам `toLocaleString("ru-RU")` |
| URL `/en/...`, hreflang | Без префикса локали; **hreflang** через `?lang=en` в `generateMetadata` (`hreflang.ts`, layouts) | Полноценные сегменты `app/[locale]` — отдельный эпик |
| Accept-Language | Не включено | Опционально в `middleware.ts` при первом визите |

## Визуальная регрессия

| Ожидание | В репо | Следующий шаг |
|----------|--------|----------------|
| Снапшоты Playwright | `e2e/visual.spec.js`, тег `@visual`; `snapshotPathTemplate` без суффикса ОС | Эталоны снимать на **Linux** (CI / Codespaces), коммитить `e2e/*-snapshots/*.png` — см. `deploy/docs/VISUAL_REGRESSION.md` |
| Зелёный CI | Основной `test:e2e` без `@visual` | Ручной или отдельный workflow `.github/workflows/e2e-visual.yml` |

## Release / флаги / on-call

| Ожидание | В репо | Следующий шаг |
|----------|--------|----------------|
| Runbook отката | `deploy/docs/RELEASE_RUNBOOK.md`, `RUNBOOK_OPERATIONS.md` | Дополнять по инцидентам |
| Build-time / env флаги | `NEXT_PUBLIC_FEATURE_*`, `WRA_*` | Runtime-флаги: контракт `GET /api/flags` + кэш на клиенте |
| Канарейка | Описана идея в runbook | Nginx `split_clients` / отдельный поддомен — ваша инфраструктура |
| On-call | Минимум в runbook | Ротация, эскалация, постмортем — процесс вне репо или `docs/postmortem-template.md` при необходимости |

## Визуал / бренд

Отдельные требования (шрифты, плотность, маркетинговые страницы) — вне этого файла; техническая база: токены + Storybook + visual e2e выше.
