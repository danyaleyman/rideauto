// @ts-check
import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:24173";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "wra-cookie-consent-v1",
        JSON.stringify({
          necessary: true,
          analytics: false,
          marketing: false,
          updatedAt: new Date().toISOString(),
        }),
      );
    } catch {
      // ignore
    }
  });
});

test.describe("визуальные снапшоты mobile", () => {
  test("catalog mobile", { tag: "@visual-mobile" }, async ({ page }) => {
    await page.goto(`${BASE}/catalog`);
    await page.waitForSelector('[data-slot="listing-card"]', { timeout: 45_000 });
    await expect(page).toHaveScreenshot("catalog-mobile.png", {
      fullPage: true,
      animations: "disabled",
      maxDiffPixelRatio: 0.06,
    });
  });

  test("buy mobile", { tag: "@visual-mobile" }, async ({ page }) => {
    await page.goto(`${BASE}/buy`);
    await expect(page).toHaveScreenshot("buy-mobile.png", {
      fullPage: true,
      animations: "disabled",
      maxDiffPixelRatio: 0.05,
    });
  });
});
