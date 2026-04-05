import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "node e2e/serve-api.mjs",
      url: "http://127.0.0.1:28765/api/health",
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "node e2e/serve-static.mjs",
      url: "http://127.0.0.1:24173/index.html",
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
