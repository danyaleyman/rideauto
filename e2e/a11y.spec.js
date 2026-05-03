// @ts-check
import { test, expect } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";

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

function seriousOrCritical(violations) {
  return violations.filter((v) => v.impact === "serious" || v.impact === "critical");
}

test("a11y: главная", async ({ page }) => {
  await page.goto(`${BASE}/`);
  const res = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(seriousOrCritical(res.violations), JSON.stringify(res.violations, null, 2)).toEqual([]);
});

test("a11y: каталог (мок)", async ({ page }) => {
  await page.goto(`${BASE}/catalog?region=korea&source=encar`);
  await page.locator('a[href^="/car/"]').first().waitFor({ state: "visible", timeout: 60_000 });
  const res = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(seriousOrCritical(res.violations), JSON.stringify(res.violations, null, 2)).toEqual([]);
});

test("a11y: как купить", async ({ page }) => {
  await page.goto(`${BASE}/buy`);
  const res = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(seriousOrCritical(res.violations), JSON.stringify(res.violations, null, 2)).toEqual([]);
});
