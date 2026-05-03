import { cookies } from "next/headers";
import type { AppLocale } from "@/lib/i18n";
import { LOCALE_COOKIE } from "@/lib/locale-constants";

export async function getServerLocale(): Promise<AppLocale> {
  try {
    const jar = await cookies();
    const v = jar.get(LOCALE_COOKIE)?.value;
    if (v === "en") return "en";
  } catch {
    // cookies() недоступен вне запроса
  }
  return "ru";
}

export { LOCALE_COOKIE } from "@/lib/locale-constants";
