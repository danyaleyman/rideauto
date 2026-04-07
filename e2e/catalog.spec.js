// @ts-check
import { test, expect } from "@playwright/test";

test("smoke flow: /catalog -> /car/[id] -> /buy", async ({ page }) => {
  await page.goto("http://127.0.0.1:24173/catalog");

  await expect(page.locator("text=Hyundai Solaris 2020").first()).toBeVisible();

  const toCar = page.locator('a[href="/car/c1"]').first();
  await expect(toCar).toBeVisible();
  await toCar.click();

  await expect(page).toHaveURL(/\/car\/c1$/);
  await expect(page.locator("h1").first()).toContainText("Hyundai");
  await expect(page.locator("text=Similar cars")).toBeVisible();

  await page.goto("http://127.0.0.1:24173/buy");
  await expect(page).toHaveURL(/\/buy$/);
  await expect(page.locator("text=How to buy a car from Korea")).toBeVisible();
  await expect(page.locator("text=Estimated total")).toBeVisible();
});
