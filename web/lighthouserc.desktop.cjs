/**
 * Lighthouse CI — desktop preset. Один build, затем замер (см. CI job lighthouse).
 *   cd web && npm run build && npm run start -- --port 3099 --hostname 127.0.0.1
 *   npx lhci autorun --config=web/lighthouserc.desktop.cjs
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
        "http://127.0.0.1:3099/catalog?region=korea",
        "http://127.0.0.1:3099/car/c1",
        "http://127.0.0.1:3099/buy",
        "http://127.0.0.1:3099/privacy",
      ],
      startServerCommand: "bash -lc 'bash web/scripts/lh-with-mock-api.sh'",
      startServerReadyPattern: "Ready in",
    },
    assert: {
      assertions: {
        "categories:performance": ["warn", { minScore: 0.72 }],
        "categories:accessibility": ["error", { minScore: 0.88 }],
        "categories:best-practices": ["error", { minScore: 0.88 }],
        "categories:seo": ["warn", { minScore: 0.9 }],
      },
    },
  },
};
