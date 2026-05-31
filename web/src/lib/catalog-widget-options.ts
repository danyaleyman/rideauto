import { createT, type AppLocale } from "@/lib/i18n";

export type CatalogWidgetOption = { value: string; label: string };

export function catalogSortOptions(locale: AppLocale): CatalogWidgetOption[] {
  const t = createT(locale);
  return [
    { value: "date_new", label: t("catalog.widgets.sortDateNew") },
    { value: "date_old", label: t("catalog.widgets.sortDateOld") },
    { value: "year_new", label: t("catalog.widgets.sortYearNew") },
    { value: "year_old", label: t("catalog.widgets.sortYearOld") },
    { value: "price_low", label: t("catalog.widgets.sortPriceLow") },
    { value: "price_high", label: t("catalog.widgets.sortPriceHigh") },
    { value: "mileage_low", label: t("catalog.widgets.sortMileageLow") },
    { value: "mileage_high", label: t("catalog.widgets.sortMileageHigh") },
  ];
}

export function catalogPricingTierOptions(locale: AppLocale): CatalogWidgetOption[] {
  const t = createT(locale);
  return [
    { value: "__any__", label: t("catalog.widgets.tierAny") },
    { value: "full_customs", label: t("catalog.widgets.tierFull") },
    { value: "korea_land_only", label: t("catalog.widgets.tierLand") },
    { value: "price_on_request", label: t("catalog.widgets.tierPor") },
  ];
}
