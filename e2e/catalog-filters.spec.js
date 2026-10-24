// @ts-check
import { test, expect } from "@playwright/test";
import { openFacetAndPick, seedCookieConsent, visibleTestId } from "./helpers/catalog.js";

const BASE = "http://127.0.0.1:24173";

test.beforeEach(async ({ page }) => {
  await seedCookieConsent(page);
});

test.describe("catalog filters", () => {
  test("desktop: mark → model cascade, URL, reset", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/catalog?region=korea`, { waitUntil: "domcontentloaded" });

    const aside = visibleTestId(page, "catalog-filters-aside");
    await expect(aside).toBeVisible({ timeout: 60_000 });
    await expect(visibleTestId(page, "catalog-facet-marks")).toBeVisible({ timeout: 60_000 });

    // Korea mock: 3 listings (card title is "Mark · Model")
    await expect(page.locator('a[href="/car/c1"]').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('a[href="/car/c3"]').first()).toBeVisible();
    await expect(page.getByText(/Hyundai\s*·\s*Solaris/i).first()).toBeVisible();

    await openFacetAndPick(page, "catalog-facet-marks", "Hyundai");
    await page.waitForURL(/marks=Hyundai/, { timeout: 20_000 });

    await expect(page.locator('a[href="/car/c3"]')).toHaveCount(0, { timeout: 20_000 });
    await expect(visibleTestId(page, "catalog-facet-models")).toBeEnabled();

    await openFacetAndPick(page, "catalog-facet-models", "Solaris");
    await page.waitForURL(/models=Solaris/, { timeout: 20_000 });
    await expect(page.locator('a[href="/car/c1"]').first()).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('a[href="/car/c2"]')).toHaveCount(0);

    await visibleTestId(page, "catalog-filters-reset").click();
    await page.waitForURL((url) => !url.searchParams.get("marks") && !url.searchParams.get("models"), {
      timeout: 20_000,
    });
    await expect(page.locator('a[href="/car/c3"]').first()).toBeVisible({ timeout: 20_000 });
    await expect(page.locator('a[href="/car/c1"]').first()).toBeVisible();
  });

  test("mobile: sheet filters apply mark to URL", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/catalog?region=korea`, { waitUntil: "domcontentloaded" });

    const openBtn = visibleTestId(page, "catalog-mobile-filters-open");
    await expect(openBtn).toBeVisible({ timeout: 60_000 });
    await openBtn.click();

    const markTrigger = visibleTestId(page, "catalog-facet-marks");
    await expect(markTrigger).toBeVisible({ timeout: 60_000 });
    await markTrigger.click();
    const option = page.getByRole("menuitemcheckbox", { name: /Hyundai/i });
    await expect(option).toBeVisible({ timeout: 15_000 });
    await option.click();
    await page.keyboard.press("Escape").catch(() => {});

    await visibleTestId(page, "catalog-mobile-filters-apply").click();
    await expect(visibleTestId(page, "catalog-mobile-filters-apply")).toBeHidden({
      timeout: 15_000,
    });
    await page.waitForURL(/marks=Hyundai/, { timeout: 20_000 });
    await expect(page.locator('a[href="/car/c3"]')).toHaveCount(0, { timeout: 20_000 });
  });
});
