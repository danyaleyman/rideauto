export const LEAD_CONTACT_OPTIONS = [
  { value: "telegram", label: "Telegram" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "phone", label: "Звонок по телефону" },
  { value: "email", label: "Электронная почта" },
] as const;

export type LeadContactMethodValue = (typeof LEAD_CONTACT_OPTIONS)[number]["value"];

export function leadContactMethodLabel(value: string): string {
  return LEAD_CONTACT_OPTIONS.find((o) => o.value === value)?.label ?? value;
}
