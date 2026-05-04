/**
 * Единая модель доступности лота на карточке (согласовано с каталогом и API).
 * В пользовательском интерфейсе не используем названия внешних площадок — только рынок/регион.
 */

import { formatPriceLabel, PRICE_ON_REQUEST_RU } from "@/lib/format-price";

export type CarListingAvailability = "available" | "reserved" | "sold";

export function getCarListingAvailability(raw: Record<string, unknown>): CarListingAvailability {
  if (raw.encar_listing_sold === true || raw.che168_listing_sold === true) return "sold";
  if (raw.encar_listing_reserved === true) return "reserved";
  return "available";
}

/** Подпись источника для UI: регион рынка, без брендов площадок. */
export function carSourceDisplayName(source: string | null | undefined): string {
  const s = (source ?? "").trim().toLowerCase();
  if (s === "encar") return "Рынок Кореи";
  if (s === "china" || s === "che168") return "Рынок Китая";
  if (!s) return "Каталог";
  return (source ?? "").trim();
}

/** Короткая метка для угла фото (бейдж). */
export function carSourceShortRegionLabel(source: string | null | undefined): string {
  const v = carSourceBadgeVariant(source);
  if (v === "encar") return "Корея";
  if (v === "china") return "Китай";
  return "Каталог";
}

export type CarSourceBadgeVariant = "encar" | "china" | "neutral";

export function carSourceBadgeVariant(source: string | null | undefined): CarSourceBadgeVariant {
  const s = (source ?? "").trim().toLowerCase();
  if (s === "encar") return "encar";
  if (s === "china" || s === "che168") return "china";
  return "neutral";
}

/** Одна строка для мобильной нижней панели и вторичных мест. */
export function carStickyPriceLine(
  availability: CarListingAvailability,
  priceOnRequest: boolean,
  rubPrice: number | null,
): string {
  if (availability === "sold") return "Автомобиль продан";
  if (availability === "reserved") return "Зарезервировано на площадке";
  if (priceOnRequest || rubPrice == null || Number.isNaN(rubPrice) || rubPrice <= 0) return PRICE_ON_REQUEST_RU;
  return formatPriceLabel(rubPrice);
}
