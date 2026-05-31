import type { TParams } from "@/lib/i18n";
import { createT, type AppLocale } from "@/lib/i18n";

export type LeadContactMethodValue = "telegram" | "whatsapp" | "phone" | "email";

type TI18n = (path: string, params?: TParams) => string;

export function leadContactOptions(t: TI18n) {
  return [
    { value: "telegram" as const, label: "Telegram" },
    { value: "whatsapp" as const, label: "WhatsApp" },
    { value: "phone" as const, label: t("buy.contactPhone") },
    { value: "email" as const, label: t("buy.contactEmail") },
  ];
}

/** @deprecated Use ``leadContactOptions(createT(locale))`` */
export const LEAD_CONTACT_OPTIONS = leadContactOptions(createT("ru"));

export function leadContactMethodLabel(value: string, locale: AppLocale = "ru"): string {
  return leadContactOptions(createT(locale)).find((o) => o.value === value)?.label ?? value;
}
