// @ts-check
import { test, expect } from "@playwright/test";
import { seedCookieConsent, visibleTestId } from "./helpers/catalog.js";
import {
  expectHoverStable,
  expectInViewport,
  expectMenuInViewport,
  expectNoHorizontalOverflow,
  expectTextNotClipped,
  expectVisibleBox,
} from "./helpers/layout.js";

const BASE = "http://127.0.0.1:24173";

test.beforeEach(async ({ page }) => {
  await seedCookieConsent(page);
});

test.describe("catalog layout geometry", () => {
  test("desktop aside facets: size, no overflow, dropdown in viewport", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/catalog?region=korea`, { waitUntil: "domcontentloaded" });

    const aside = visibleTestId(page, "catalog-filters-aside");
    await expect(aside).toBeVisible({ timeout: 60_000 });
    await expectNoHorizontalOverflow(aside);

    const facetIds = [
      "catalog-facet-marks",
      "catalog-facet-clusters",
      "catalog-facet-models",
      "catalog-facet-body",
      "catalog-facet-fuel",
      "catalog-facet-transmission",
    ];
    for (const id of facetIds) {
      const trigger = visibleTestId(page, id);
      await trigger.scrollIntoViewIfNeeded();
      await expectVisibleBox(trigger, { minW: 40, minH: 36 });
      await expectInViewport(page, trigger, { pad: 4 });
      await expectTextNotClipped(trigger);
    }

    const market = visibleTestId(page, "catalog-market");
    await expectVisibleBox(market, { minW: 120, minH: 40 });
    await expectHoverStable(page, visibleTestId(page, "catalog-market-korea"));

    const marks = visibleTestId(page, "catalog-facet-marks");
    await marks.click();
    const menu = page.locator('[data-slot="dropdown-menu-content"]').filter({ visible: true }).first();
    await expectMenuInViewport(page, menu);
    const item = page.getByRole("menuitemcheckbox", { name: /Hyundai/i });
    await expectVisibleBox(item, { minW: 40, minH: 28 });
    await page.keyboard.press("Escape");

    const reset = visibleTestId(page, "catalog-filters-reset");
    await expectVisibleBox(reset, { minW: 40, minH: 36 });
    await expectHoverStable(page, reset);
  });

  test("desktop card CTA hover does not jump layout", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(`${BASE}/catalog?region=korea`, { waitUntil: "domcontentloaded" });

    const cardLink = page.locator('a[href="/car/c1"]').first();
    await expect(cardLink).toBeVisible({ timeout: 60_000 });
    await expectHoverStable(page, cardLink, { tolerance: 2 });
  });

  test("mobile filters open/apply are usable and in viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/catalog?region=korea`, { waitUntil: "domcontentloaded" });

    const openBtn = visibleTestId(page, "catalog-mobile-filters-open");
    await expect(openBtn).toBeVisible({ timeout: 60_000 });
    await expectVisibleBox(openBtn, { minW: 40, minH: 40 });
    await expectInViewport(page, openBtn, { pad: 2 });
    await expectHoverStable(page, openBtn, { tolerance: 2 });

    await openBtn.click();
    await expect(page.getByRole("dialog").filter({ visible: true }).first()).toBeVisible({
      timeout: 15_000,
    });
    const apply = page.getByTestId("catalog-mobile-filters-apply");
    await expect(apply).toBeVisible({ timeout: 15_000 });
    await expectVisibleBox(apply, { minW: 40, minH: 40 });
    await expectInViewport(page, apply, { pad: 8 });

    const mark = page
      .getByRole("dialog")
      .getByTestId("catalog-facet-marks")
      .filter({ visible: true })
      .first();
    await expect(mark).toBeVisible({ timeout: 60_000 });
    await mark.scrollIntoViewIfNeeded();
    await expectVisibleBox(mark, { minW: 40, minH: 36 });
    await expectTextNotClipped(mark);
  });
});
