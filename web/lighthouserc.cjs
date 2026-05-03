/**
 * Lighthouse CI: статичные страницы без обязательного API (каталог в CI может быть пустым).
 * Запуск из корня репозитория после `npm ci && cd web && npm run build`:
 *   PORT=3099 npm run lh:ci
 */
module.exports = {
  ci: {
    collect: {
      numberOfRuns: 1,
      settings: {
        preset: "desktop",
        throttling: { rttMs: 40, throughputKbps: 10 * 1024, cpuSlowdownMultiplier: 1 },
      },
      url: [
        "http://127.0.0.1:3099/",
        "http://127.0.0.1:3099/about",
        "http://127.0.0.1:3099/privacy",
        "http://127.0.0.1:3099/buy",
      ],
      startServerCommand:
        "bash -lc 'cd web && npm run start -- --port 3099 --hostname 127.0.0.1'",
      startServerReadyPattern: "Ready in",
    },
    assert: {
      assertions: {
        // PR: при отключённом perf зелёный CI не ловит регрессии. Сначала warn; жёсткий error — на стейдже (см. lighthouserc.staging.example.cjs).
        "categories:performance": ["warn", { minScore: 0.72 }],
        "categories:accessibility": ["error", { minScore: 0.88 }],
        "categories:best-practices": ["error", { minScore: 0.88 }],
        "categories:seo": ["warn", { minScore: 0.9 }],
      },
    },
  },
};
