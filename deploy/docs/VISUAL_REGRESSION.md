# Визуальная регрессия (Playwright)

## Зачем

Снапшоты завязаны на **шрифты и рендер ОС**. Один и тот же тест на Windows и Ubuntu даёт разный PNG — в CI (Ubuntu) эталоны должны соответствовать **Linux**.

## Где тесты

- `e2e/visual.spec.js` — тег `@visual` (desktop 1280×800).
- `e2e/visual-mobile.spec.js` — тег `@visual-mobile` (iPhone 14 + Pixel 7 в Playwright).
- Корневой `npm run test:e2e` **исключает** `@visual` (меньше шума на локальных ОС).
- `npm run test:e2e:visual` — все визуальные (desktop + mobile projects).

## Имена файлов

В `playwright.config.mjs` снапшоты лежат по проектам: `e2e/visual.spec.js-snapshots/visual-desktop/privacy.png`, `…/visual-iphone/catalog-mobile.png`, `…/visual-pixel/catalog-mobile.png`.

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
