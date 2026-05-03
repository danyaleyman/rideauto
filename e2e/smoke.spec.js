// @ts-check
import { test, expect } from "@playwright/test";

const BASE = "http://127.0.0.1:24173";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    try {
      localStorage.removeItem("wra-cookie-consent-v1");
    } catch {
      // ignore
    }
  });
});

test("главная: герой и ссылка в каталог", async ({ page }) => {
  await page.goto(`${BASE}/`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Кореи|Китая/);
  await expect(page.getByRole("link", { name: "Открыть каталог" })).toBeVisible();
});

test("каталог с параметрами и карточка", async ({ page }) => {
  await page.goto(`${BASE}/catalog?region=korea&q=Hyundai&source=encar`);
  const toCar = page.locator('a[href="/car/c1"]').first();
  await expect(toCar).toBeVisible({ timeout: 60_000 });
  await toCar.click();
  await expect(page).toHaveURL(/\/car\/c1/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(/Hyundai/i);
  await expect(page.getByText("Похожие автомобили")).toBeVisible();
});

test("страница «Как купить»: якоря и отправка заявки (мок API)", async ({ page }) => {
  await page.goto(`${BASE}/buy`);
  await expect(page.getByRole("heading", { name: "Как купить автомобиль" })).toBeVisible();

  await page.getByRole("link", { name: "Этапы" }).click();
  await expect(page.locator("#buy-step-1")).toBeVisible();

  await page.getByRole("button", { name: "Только необходимые" }).click();

  await page.getByLabel("ФИО").fill("Иванов Иван");
  await page.getByLabel("Автомобиль и пожелания").fill("Тестовая заявка e2e, подбор Hyundai до 2 млн.");
  await page.getByRole("checkbox", { name: "Согласие на обработку персональных данных" }).click();
  await page.getByRole("button", { name: "Отправить заявку" }).click();
  await expect(page.getByText("Ваша заявка отправлена")).toBeVisible({ timeout: 30_000 });
});

test("cookie-баннер на мобильной ширине не перекрывает критичный контент полностью", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE}/`);
  const banner = page.getByRole("button", { name: "Принять" });
  await expect(banner).toBeVisible();
  await expect(page.getByRole("link", { name: "Политике cookie" })).toBeVisible();
});
