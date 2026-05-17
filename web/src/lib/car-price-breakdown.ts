import { formatPriceLabel } from "@/lib/format-price";
import { shouldShowImportExciseVatBreakdown } from "@/lib/engine-fuel";
import { extractPricingTier } from "@/lib/pricing-tier-ui";

export type PriceBreakdownRow = {
  label: string;
  value: string;
  note?: string;
  subRows?: { label: string; value: string }[];
};

const EPS = 0.01;

export function numCalcField(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, "").replace(",", "."));
  if (!Number.isFinite(n)) return null;
  return n;
}

function hasAmount(n: number | null): n is number {
  return n != null && Math.abs(n) > EPS;
}

export function isChinaListing(data: Record<string, unknown>, carId?: string): boolean {
  const src = String(data.source ?? "").toLowerCase();
  if (src === "che168" || src === "china") return true;
  const id = String(carId ?? data.id ?? data.car_id ?? "").toLowerCase();
  return id.startsWith("che168-");
}

function formatForeignListingLine(
  foreignLabel: string,
  foreignAmount: number,
  rubAmount: number | null,
): string {
  const foreign = `${Math.round(foreignAmount).toLocaleString("ru-RU")} ${foreignLabel}`;
  if (rubAmount != null && rubAmount > EPS) {
    return `${foreign} (${formatPriceLabel(rubAmount)})`;
  }
  return foreign;
}

function filterSubRows(rows: { label: string; value: string }[]): { label: string; value: string }[] {
  return rows.filter((r) => r.value !== "—");
}

function appendSection(
  rows: PriceBreakdownRow[],
  label: string,
  total: number | null,
  subRows: { label: string; value: string }[],
  note?: string,
): void {
  const subs = filterSubRows(subRows);
  if (!hasAmount(total) && subs.length === 0) return;
  rows.push({
    label,
    value: hasAmount(total) ? formatPriceLabel(total) : subs.length === 1 ? subs[0].value : "—",
    note,
    subRows: subs.length > 1 || (subs.length === 1 && hasAmount(total)) ? subs : undefined,
  });
}

export type BuildPriceBreakdownInput = {
  priceRub: number | null;
  priceOnRequest?: boolean;
  priceWon?: number | null;
  priceCny?: number | null;
  carId?: string;
  calcDetails?: Record<string, unknown> | null;
  listingUnavailable?: boolean;
};

/** Единая раскладка «Подробный расчёт» для карточки авто (Корея / Китай). */
export function buildPriceBreakdownRows(input: BuildPriceBreakdownInput): PriceBreakdownRow[] {
  const {
    priceRub,
    priceOnRequest = false,
    priceWon = null,
    priceCny = null,
    carId,
    calcDetails,
    listingUnavailable = false,
  } = input;
  const d = calcDetails ?? {};
  const rows: PriceBreakdownRow[] = [];
  const china = isChinaListing(d, carId);
  const tier = extractPricingTier(d);
  const showCustoms = tier === "full_customs";

  if (!listingUnavailable && !priceOnRequest && priceRub != null && !Number.isNaN(priceRub) && priceRub > EPS) {
    rows.push({
      label: "Стоимость в России под ключ",
      value: formatPriceLabel(priceRub),
    });
  }

  if (!china && priceWon != null && !Number.isNaN(priceWon)) {
    const wonTotal = priceWon >= 100_000 ? priceWon : priceWon * 10_000;
    const rubPerWon =
      numCalcField(d.cbr_krw_rub_per_won) ??
      numCalcField(d.krw_pricing_rub_per_won) ??
      numCalcField(d.rub_pw);
    const listingRub =
      rubPerWon != null && rubPerWon > 0 ? wonTotal * rubPerWon : numCalcField(d.price_rub_estimate);
    rows.push({
      label: "Цена в объявлении (воны)",
      value: formatForeignListingLine("₩", wonTotal, listingRub),
      note: "Только стоимость автомобиля в стране продажи, без оформления и доставки; в скобках — ориентир по курсу ЦБ.",
    });
  }

  if (china) {
    const cny =
      priceCny != null && !Number.isNaN(priceCny)
        ? priceCny
        : numCalcField(d.price_cny);
    if (cny != null && cny > EPS) {
      const cnyRub = numCalcField(d.cny_rub);
      const listingRub =
        cnyRub != null && cnyRub > 0
          ? cny * cnyRub
          : numCalcField(d.price_rub_estimate);
      rows.push({
        label: "Цена в объявлении (CNY)",
        value: formatForeignListingLine("CN¥", cny, listingRub),
        note: "Только цена автомобиля в Китае; в скобках — пересчёт по курсу ЦБ, не итог под ключ.",
      });
    }
  }

  const duty = numCalcField(d.duty_rub);
  const customsFee = numCalcField(d.customs_fee_rub);
  const util = numCalcField(d.util_rub);
  const excise = numCalcField(d.excise_rub);
  const vat = numCalcField(d.vat_rub);
  const showExciseVat = shouldShowImportExciseVatBreakdown(d, excise, vat);
  const customsTotal = numCalcField(d.customs_total_rub);

  if (showCustoms) {
    const customsSubRows: { label: string; value: string }[] = [];
    if (hasAmount(duty)) customsSubRows.push({ label: "Пошлина", value: formatPriceLabel(duty) });
    if (hasAmount(customsFee)) {
      customsSubRows.push({ label: "Таможенный сбор", value: formatPriceLabel(customsFee) });
    }
    if (hasAmount(util)) {
      customsSubRows.push({ label: "Утилизационный сбор", value: formatPriceLabel(util) });
    }
    if (showExciseVat) {
      if (hasAmount(excise)) {
        customsSubRows.push({ label: "Акциз (СТП)", value: formatPriceLabel(excise) });
      }
      if (hasAmount(vat)) {
        customsSubRows.push({ label: "НДС (СТП)", value: formatPriceLabel(vat) });
      }
    }
    appendSection(
      rows,
      "Таможенные расходы",
      customsTotal,
      customsSubRows,
      "Для физлица: на бензин/дизель/гибрид — пошлина, сбор и утилизация; на электро — СТП (пошлина, акциз, НДС).",
    );
  }

  const freight = numCalcField(d.freight_rub);
  const docsKorea = numCalcField(d.documents_krw_rub);
  const docsChina = numCalcField(d.china_docs_delivery_rub);
  const vtb = numCalcField(d.vtb_bank_transfer_rub);

  const logisticsSubRows: { label: string; value: string }[] = [];
  if (china) {
    if (hasAmount(docsChina)) {
      logisticsSubRows.push({
        label: "Оформление в Китае и доставка до таможни",
        value: formatPriceLabel(docsChina),
      });
    }
    if (hasAmount(vtb)) {
      logisticsSubRows.push({
        label: "Банковский перевод (ВТБ 2%)",
        value: formatPriceLabel(vtb),
      });
    }
    if (hasAmount(freight)) {
      logisticsSubRows.push({ label: "Доставка / порт", value: formatPriceLabel(freight) });
    }
  } else {
    if (hasAmount(freight)) {
      logisticsSubRows.push({ label: "Доставка / фрахт", value: formatPriceLabel(freight) });
    }
    if (hasAmount(docsKorea)) {
      logisticsSubRows.push({
        label: "Оформление документов (Корея)",
        value: formatPriceLabel(docsKorea),
      });
    }
  }
  const logisticsTotal =
    (hasAmount(freight) ? freight : 0) +
    (hasAmount(docsKorea) ? docsKorea : 0) +
    (hasAmount(docsChina) ? docsChina : 0) +
    (hasAmount(vtb) ? vtb : 0);
  appendSection(
    rows,
    "Логистика и портовые расходы",
    logisticsTotal > EPS ? logisticsTotal : null,
    logisticsSubRows,
  );

  const broker = numCalcField(d.broker_rub);
  if (hasAmount(broker)) {
    rows.push({
      label: "Брокерские услуги",
      value: formatPriceLabel(broker),
      note: "В сумму входят СБКТС, ЭПТС и регистрационные платежи в РФ.",
    });
  }

  const commission = numCalcField(d.commission_rub);
  if (hasAmount(commission)) {
    rows.push({
      label: "Комиссия Ride Auto",
      value: formatPriceLabel(commission),
    });
  }

  return rows;
}
