// @ts-check
/** @tag @funnel */
import { test, expect } from "@playwright/test";

test.describe.configure({ tag: "@funnel" });

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

test("b2c: compare from catalog adds item and opens compare page", async ({ page }) => {
  await page.goto(`${BASE}/catalog`);
  await page.getByRole("button", { name: "Добавить в сравнение" }).first().click();
  await page.getByRole("link", { name: /Сравнение/i }).first().click();
  await expect(page).toHaveURL(/\/compare/);
  await expect(page.getByRole("heading", { name: /Сравнение автомобилей/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Hyundai/i }).first()).toBeVisible({ timeout: 15_000 });
});

test("b2c: save catalog search to localStorage when logged out", async ({ page }) => {
  await page.goto(`${BASE}/catalog`);
  await page.getByRole("button", { name: "Сохранить поиск" }).click();
  await expect(page.getByLabel("Сохранённые поиски")).toBeVisible({ timeout: 10_000 });
  const saved = await page.evaluate(() => localStorage.getItem("wra-saved-catalog-searches-v1"));
  expect(saved).toBeTruthy();
});

test("b2c: account page redirects to login when logged out", async ({ page }) => {
  await page.goto(`${BASE}/account`);
  await page.waitForURL(/\/login/, { timeout: 15_000 });
  expect(page.url()).toContain("/login");
});
