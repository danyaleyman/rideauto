import { buildNormalizedCarTitle, normalizeCatalogDisplayLabel } from "@/lib/car-detail-data";
import { enrichChe168CarSpecs } from "@/lib/che168-spec-enrich";
import type { SlimCar } from "@/lib/types";

/** Нормализованные поля карточки каталога для chips и заголовка. */
export function buildCatalogCardDisplayData(car: SlimCar): {
  cardData: Record<string, unknown>;
  normalizedTitle: string;
} {
  const cardDataRaw = (car.data ?? {}) as Record<string, unknown>;
  const carObj = car as unknown as Record<string, unknown>;
  const rawReadModel = carObj.read_model;
  const cardReadModel =
    rawReadModel && typeof rawReadModel === "object" && !Array.isArray(rawReadModel)
      ? (rawReadModel as Record<string, unknown>)
      : {};
  const merged: Record<string, unknown> = {
    ...cardDataRaw,
    year: cardDataRaw.year ?? cardReadModel.year ?? car.year_num,
    yearMonth: cardDataRaw.yearMonth ?? cardReadModel.yearMonth ?? cardReadModel.year_month,
    km_age: cardDataRaw.km_age ?? cardReadModel.mileage_km,
    power_hp: cardDataRaw.power_hp ?? cardReadModel.power_hp,
    displacement_cc: cardDataRaw.displacement_cc ?? cardReadModel.displacement_cc,
    displacement:
      cardDataRaw.displacement ??
      cardReadModel.displacement ??
      cardDataRaw.che168_displacement_label ??
      cardReadModel.che168_displacement_label,
    che168_displacement_label:
      cardDataRaw.che168_displacement_label ?? cardReadModel.che168_displacement_label,
    engine_type: cardDataRaw.engine_type ?? cardReadModel.engine_type,
    transmission_type: cardDataRaw.transmission_type ?? cardReadModel.transmission_type,
    transmission_type_ru: cardDataRaw.transmission_type_ru ?? cardReadModel.transmission_type_ru,
    drive_type: cardDataRaw.drive_type ?? cardReadModel.drive_type,
    body_type: cardDataRaw.body_type ?? cardReadModel.body_type,
    color: cardDataRaw.color ?? cardReadModel.color,
    source:
      cardDataRaw.source ??
      cardReadModel.source ??
      (String(car.id).toLowerCase().startsWith("che168-") ? "che168" : undefined),
    engine: cardDataRaw.engine,
    che168_params_raw: cardDataRaw.che168_params_raw,
  };
  const cardData = enrichChe168CarSpecs(merged);
  const normalizedTitle =
    buildNormalizedCarTitle(
      cardData.mark,
      cardData.model,
      cardData.generation ?? cardData.configuration,
      cardData.source,
    ) ||
    normalizeCatalogDisplayLabel(car.title) ||
    car.id;
  return { cardData, normalizedTitle };
}
