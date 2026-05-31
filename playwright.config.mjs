import { defineConfig, devices } from "@playwright/test";

const isStaging = process.env.E2E_STAGING === "1";

const mockApi = {
  command: "node e2e/serve-mock-api.mjs",
  url: "http://127.0.0.1:28765/api/health",
  timeout: 30_000,
  reuseExistingServer: !process.env.CI,
};

const nextDefault = {
  command: "node e2e/serve-next.mjs",
  url: "http://127.0.0.1:24173/",
  timeout: 120_000,
  reuseExistingServer: !process.env.CI,
};

const nextVirtual = {
  command: "node e2e/serve-next-virtual.mjs",
  url: "http://127.0.0.1:24174/",
  timeout: 120_000,
  reuseExistingServer: !process.env.CI,
};

export default defineConfig({
  testDir: "e2e",
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  snapshotPathTemplate: "{testDir}/{testFilePath}-snapshots/{projectName}/{arg}{ext}",
  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  expect: {
    timeout: 30_000,
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.04,
      animations: "disabled",
    },
  },
  ...(isStaging
    ? {
        grep: /@staging/,
      }
    : {
        grepInvert: /@staging/,
        projects: [
          {
            name: "default",
            grepInvert: /@visual|@visual-mobile|@virtual-scroll|@funnel/,
            use: { baseURL: "http://127.0.0.1:24173" },
          },
          {
            name: "visual-desktop",
            grep: /@visual/,
            grepInvert: /@visual-mobile/,
            use: { baseURL: "http://127.0.0.1:24173", viewport: { width: 1280, height: 800 } },
          },
          {
            name: "visual-iphone",
            grep: /@visual-mobile/,
            use: {
              browserName: "chromium",
              ...devices["iPhone 14"],
              baseURL: "http://127.0.0.1:24173",
            },
          },
          {
            name: "visual-pixel",
            grep: /@visual-mobile/,
            use: { ...devices["Pixel 7"], baseURL: "http://127.0.0.1:24173" },
          },
          {
            name: "virtual-catalog",
            grep: /@virtual-scroll/,
            use: { baseURL: "http://127.0.0.1:24174" },
            webServer: [mockApi, nextVirtual],
          },
        ],
        webServer: [mockApi, nextDefault],
      }),
});
