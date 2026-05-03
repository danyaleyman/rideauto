import type { AppLocale } from "@/lib/i18n";

const localeTag: Record<AppLocale, string> = {
  ru: "ru-RU",
  en: "en-US",
};

export function formatCurrencyLocale(amount: number, locale: AppLocale): string {
  return new Intl.NumberFormat(localeTag[locale], {
    style: "currency",
    currency: "RUB",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatIntegerLocale(n: number, locale: AppLocale): string {
  return new Intl.NumberFormat(localeTag[locale], { maximumFractionDigits: 0 }).format(n);
}

export function formatDateLocale(iso: string | Date, locale: AppLocale, opts?: Intl.DateTimeFormatOptions): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  return new Intl.DateTimeFormat(localeTag[locale], opts ?? { dateStyle: "medium" }).format(d);
}
