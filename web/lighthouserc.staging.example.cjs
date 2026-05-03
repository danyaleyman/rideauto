/**
 * Пример жёстких порогов для стейджа/CDN (скопировать в CI или запускать вручную):
 *
 *   STAGING_ORIGIN=https://staging.rideauto.ru npx lhci autorun --config=web/lighthouserc.staging.example.cjs
 *
 * В ``collect.url`` подставьте реальные публичные URL (не localhost).
 */
const origin = (process.env.STAGING_ORIGIN || "https://rideauto.ru").replace(/\/$/, "");

module.exports = {
  ci: {
    collect: {
      numberOfRuns: 2,
      settings: { preset: "desktop" },
      url: [`${origin}/`, `${origin}/catalog`, `${origin}/buy`],
    },
    assert: {
      assertions: {
        "categories:performance": ["error", { minScore: 0.78 }],
        "categories:accessibility": ["error", { minScore: 0.9 }],
        "categories:best-practices": ["error", { minScore: 0.9 }],
        "categories:seo": ["error", { minScore: 0.92 }],
        "first-contentful-paint": ["warn", { maxNumericValue: 2500 }],
        "interactive": ["warn", { maxNumericValue: 5500 }],
      },
    },
  },
};
