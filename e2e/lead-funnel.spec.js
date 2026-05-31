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

test("funnel: buy page lead form submits", async ({ page }) => {
  await page.goto(`${BASE}/buy`);
  await page.getByLabel(/^ФИО$/i).fill("Иванов Иван Иванович");
  await page.getByLabel(/Автомобиль и пожелания/i).fill("E2E: интересует Hyundai Tucson из Кореи, бюджет до 3 млн.");
  await page.getByRole("checkbox", { name: /согласие на обработку/i }).click();
  await page.getByRole("button", { name: /Отправить заявку/i }).click();
  await expect(page.getByText(/Ваша заявка отправлена/i)).toBeVisible({ timeout: 20_000 });
});

test("funnel: catalog legacy source redirects to clean url", async ({ page }) => {
  const res = await page.goto(`${BASE}/catalog?source=encar&marks=Hyundai`);
  expect(res?.status()).toBeLessThan(400);
  await page.waitForURL(/\/catalog\?marks=Hyundai/, { timeout: 15_000 });
  expect(page.url()).not.toMatch(/source=/);
  expect(page.url()).not.toMatch(/encar|che168/);
});
