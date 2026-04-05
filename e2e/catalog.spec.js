// @ts-check
import { test, expect } from "@playwright/test";

test("каталог получает /api/cars с отдельного origin", async ({ page }) => {
  await page.addInitScript(() => {
    window.WRA_API_BASE = "http://127.0.0.1:28765";
  });
  const carsOk = page.waitForResponse(
    (r) =>
      r.url().includes("127.0.0.1:28765") &&
      r.url().includes("/api/cars") &&
      r.status() === 200,
  );
  await page.goto("http://127.0.0.1:24173/index.html");
  await carsOk;
  await expect(page.locator("#grid")).toBeVisible();
});
