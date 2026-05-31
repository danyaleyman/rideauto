// @ts-check
import { test, expect } from "@playwright/test";

test.describe("catalog virtual list scroll @virtual-scroll", () => {
  test.use({ baseURL: "http://127.0.0.1:24174" });

  test("window scroll works with filters aside visible", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("/catalog?region=korea", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 30_000 });

    const aside = page.locator("aside").first();
    await expect(aside).toBeVisible();

    const y0 = await page.evaluate(() => window.scrollY);
    await page.evaluate(() => window.scrollBy({ top: 720, behavior: "instant" }));
    await page.waitForTimeout(400);
    const y1 = await page.evaluate(() => window.scrollY);
    expect(y1).toBeGreaterThan(y0);

    await aside.locator("input").first().click({ timeout: 5000 }).catch(() => {});
    await page.evaluate(() => window.scrollBy({ top: 400, behavior: "instant" }));
    const y2 = await page.evaluate(() => window.scrollY);
    expect(y2).toBeGreaterThan(y1);
  });
});
