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

test.describe("визуальные снапшоты (статичные страницы)", () => {
  test("privacy", { tag: "@visual" }, async ({ page }) => {
    await page.goto(`${BASE}/privacy`);
    await expect(page).toHaveScreenshot("privacy.png", {
      fullPage: true,
      animations: "disabled",
      maxDiffPixelRatio: 0.03,
    });
  });

  test("cookies", { tag: "@visual" }, async ({ page }) => {
    await page.goto(`${BASE}/cookies`);
    await expect(page).toHaveScreenshot("cookies.png", {
      fullPage: true,
      animations: "disabled",
      maxDiffPixelRatio: 0.03,
    });
  });

  test("buy", { tag: "@visual" }, async ({ page }) => {
    await page.goto(`${BASE}/buy`);
    await expect(page).toHaveScreenshot("buy.png", {
      fullPage: true,
      animations: "disabled",
      maxDiffPixelRatio: 0.04,
    });
  });
});
