// @ts-check
import { test, expect } from "@playwright/test";

const origin = process.env.STAGING_WEB_ORIGIN?.replace(/\/$/, "") || "https://rideauto.ru";

test.describe("staging smoke @staging", () => {
  test("home responds", async ({ page }) => {
    const res = await page.goto(`${origin}/`, { waitUntil: "domcontentloaded" });
    expect(res?.status()).toBeLessThan(500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("catalog responds with listings", async ({ page }) => {
    const res = await page.goto(`${origin}/catalog?region=korea`, {
      waitUntil: "domcontentloaded",
    });
    expect(res?.status()).toBeLessThan(500);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const cards = page.locator('a[href^="/car/"]');
    await expect(cards.first()).toBeVisible({ timeout: 30_000 });
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test("api health on real origin", async ({ request }) => {
    const res = await request.get(`${origin}/api/health`);
    expect(res.status()).toBeLessThan(500);
    const json = await res.json();
    expect(json.status).toBe("ok");
  });

  test("api deep health — postgres, redis, meilisearch", async ({ request }) => {
    const res = await request.get(`${origin}/api/health?deep=1`);
    expect(res.status()).toBeLessThan(500);
    const json = await res.json();
    expect(["ok", "degraded"]).toContain(json.status);
    expect(json.checks?.postgres?.ok).toBe(true);
    expect(json.checks?.meilisearch?.ok).toBe(true);
    expect(json.checks?.meilisearch?.stale).not.toBe(true);
  });

  test("car page from catalog link", async ({ page }) => {
    await page.goto(`${origin}/catalog?region=korea`, { waitUntil: "domcontentloaded" });
    const first = page.locator('a[href^="/car/"]').first();
    await expect(first).toBeVisible({ timeout: 30_000 });
    const href = await first.getAttribute("href");
    expect(href).toMatch(/^\/car\//);
    const res = await page.goto(`${origin}${href}`, { waitUntil: "domcontentloaded" });
    expect(res?.status()).toBeLessThan(500);
    await expect(page.locator("h1").first()).toBeVisible();
  });
});
