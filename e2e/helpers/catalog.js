// @ts-check
/**
 * Shared catalog e2e helpers (consent, visible locators, facet pick).
 */

/**
 * @param {import('@playwright/test').Page} page
 */
export async function seedCookieConsent(page) {
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
}

/**
 * Visible instance of a test id (page may mount desktop+mobile duplicates).
 * @param {import('@playwright/test').Page} page
 * @param {string} testId
 */
export function visibleTestId(page, testId) {
  return page.getByTestId(testId).filter({ visible: true }).first();
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {string} facetTestId
 * @param {string} optionName
 */
export async function openFacetAndPick(page, facetTestId, optionName) {
  const { expect } = await import("@playwright/test");
  const trigger = visibleTestId(page, facetTestId);
  await expect(trigger).toBeEnabled({ timeout: 60_000 });
  await trigger.click();
  const option = page.getByRole("menuitemcheckbox", { name: new RegExp(optionName, "i") });
  await expect(option).toBeVisible({ timeout: 15_000 });
  await option.click();
  await page.keyboard.press("Escape").catch(() => {});
}
