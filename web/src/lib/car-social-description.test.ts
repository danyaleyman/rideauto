import { describe, expect, it } from "vitest";
import { buildCarSocialDescription } from "@/lib/car-social-description";

describe("buildCarSocialDescription", () => {
  it("formats core blocks and equipment lines", () => {
    const text = buildCarSocialDescription({
      carId: "41704526",
      title: "Chevrolet Trailblazer 1.3 Turbo 2WD",
      priceRub: 1_520_000,
      publishedAt: "2026-05-19",
      data: {
        engine_type: "бензин",
        displacement_cc: 1300,
        power_hp: 156,
        power_kw: 115,
        torque_nm: 236,
        drive_type: "FWD",
        transmission_type: "automatic",
        yearMonth: 202204,
        km_age: 34173,
        trim_name: "RS",
        che168_recommended_options: ["Адаптивный круиз-контроль", "Камера заднего вида"],
      },
    });

    expect(text).toContain("🚘 Chevrolet Trailblazer");
    expect(text).toContain("/car/41704526");
    expect(text).toContain("• Двигатель:");
    expect(text).toContain("• Мощность: 156 л.с. (115 кВт)");
    expect(text).toContain("• Крутящий момент: 236 Н·м");
    expect(text).toContain("• Привод: передний — 2WD / FWD");
    expect(text).toContain("• Трансмиссия: автоматическая");
    expect(text).toContain("• Дата выпуска: 2022.04");
    expect(text).toContain("• Пробег:");
    expect(text).toContain("Комплектация RS:");
    expect(text).toContain("> Адаптивный круиз-контроль");
    expect(text.replace(/\u00a0/g, " ")).toContain("💳 Цена во Владивостоке под ключ: 1 520 000 руб.");
    expect(text).toContain("19.05.2026");
  });
});
