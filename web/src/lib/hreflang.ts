import { getSiteUrl } from "@/lib/env";

/** Убираем/ставим ``lang=`` для альтернативных URL (cookie-локаль без префикса ``/en``). */
function searchForLocale(search: string, locale: "ru" | "en"): string {
  const raw = search.startsWith("?") ? search.slice(1) : search;
  const q = new URLSearchParams(raw);
  if (locale === "en") q.set("lang", "en");
  else q.delete("lang");
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** Абсолютные URL для ``metadata.alternates`` (SEO-hreflang при модели ``?lang=en``). */
export function buildLocaleAlternates(
  pathname: string,
  search: string,
): { canonical: string; languages: Record<string, string> } {
  const base = getSiteUrl().replace(/\/$/, "");
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  const ruQ = searchForLocale(search, "ru");
  const enQ = searchForLocale(search, "en");
  const ruUrl = `${base}${path}${ruQ}`;
  const enUrl = `${base}${path}${enQ}`;
  return {
    canonical: ruUrl,
    languages: {
      "ru-RU": ruUrl,
      "en-US": enUrl,
      "x-default": ruUrl,
    },
  };
}
