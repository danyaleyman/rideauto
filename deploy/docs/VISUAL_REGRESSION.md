# Визуальная регрессия (Playwright)

## Зачем

Снапшоты завязаны на **шрифты и рендер ОС**. Один и тот же тест на Windows и Ubuntu даёт разный PNG — в CI (Ubuntu) эталоны должны соответствовать **Linux**.

## Где тесты

- `e2e/visual.spec.js` — тег `@visual`.
- Корневой `npm run test:e2e` **исключает** `@visual` (меньше шума на локальных ОС).
- `npm run test:e2e:visual` — только визуальные.

## Имена файлов

В `playwright.config.mjs` задано `snapshotPathTemplate` **без суффикса `-linux`/`-win32`** — в репозитории один набор файлов, например `e2e/visual.spec.js-snapshots/privacy.png`.

## Как обновить эталоны (рекомендуется Linux)

На машине с Ubuntu / GitHub Codespaces / CI job с `ubuntu-latest`:

```bash
git clone … && cd rideauto
npm ci
cd web && npm ci && cd ..
# при необходимости: cd web && npm run build
npx playwright install chromium --with-deps
npm run test:e2e:visual -- --update-snapshots
git add e2e/visual.spec.js-snapshots
git commit -m "chore(e2e): refresh visual snapshots"
```

## Ручной прогон в GitHub Actions

Workflow **E2E Visual** (`.github/workflows/e2e-visual.yml`): **Actions → E2E Visual → Run workflow**. Не блокирует основной CI; при отсутствии закоммиченных PNG шаг упадёт до первой заливки эталонов.
