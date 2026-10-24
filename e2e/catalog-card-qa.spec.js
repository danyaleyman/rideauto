// @ts-check
/**
 * Visual QA: listing cards across Korea / China / USA × desktop + mobile.
 * Structural asserts + screenshots (first run creates baselines).
 */
import { test, expect } from "@playwright/test";
import { seedCookieConsent } from "./helpers/catalog.js";

async function openMarket(page, market) {
  const qs = market === "korea" ? "" : `?region=${market}`;
  await page.goto(`/catalog${qs}`);
  await page.waitForSelector('[data-slot="listing-card"]', { timeout: 60_000 });
  const card = page.locator('[data-slot="listing-card"]').first();
  await expect(card).toBeVisible();
  return card;
}

test.beforeEach(async ({ page }) => {
  await seedCookieConsent(page);
});

for (const market of ["korea", "china", "usa"]) {
  test.describe(`catalog card QA ${market}`, () => {
    test(`desktop meta line @visual`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 800 });
      const card = await openMarket(page, market);
      const meta = card.locator('p[aria-label="Краткие характеристики"], p[aria-label="Quick specs"]');
      await expect(meta).toBeVisible();
      const text = (await meta.innerText()).replace(/\s+/g, " ").trim();
      expect(text.length).toBeGreaterThan(3);
      // Market label present in meta line.
      if (market === "korea") expect(text).toMatch(/Корея|Korea/i);
      if (market === "china") expect(text).toMatch(/Китай|China/i);
      if (market === "usa") expect(text).toMatch(/США|USA/i);
      await expect(card.getByText(/Продано|Sold\b/i)).toHaveCount(0);
      // Chip cloud removed from SRP body.
      await expect(card.locator("ul[aria-label]")).toHaveCount(0);
      await expect(card).toHaveScreenshot(`card-${market}-desktop.png`, {
        animations: "disabled",
        maxDiffPixelRatio: 0.08,
      });
    });

    test(`mobile meta line @visual-mobile`, async ({ page }) => {
      const card = await openMarket(page, market);
      const meta = card.locator('p[aria-label="Краткие характеристики"], p[aria-label="Quick specs"]');
      await expect(meta).toBeVisible();
      await expect(card.getByText(/Продано|Sold\b/i)).toHaveCount(0);
      await expect(card.locator("ul[aria-label]")).toHaveCount(0);
      await expect(card).toHaveScreenshot(`card-${market}-mobile.png`, {
        animations: "disabled",
        maxDiffPixelRatio: 0.08,
      });
    });
  });
}
