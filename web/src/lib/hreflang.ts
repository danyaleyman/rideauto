import { getSiteUrl } from "@/lib/env";

const LOCALE_PREFIX = /^\/(en|ru)(?=\/|$)/;

function stripLocalePrefix(pathname: string): string {
  const m = pathname.match(LOCALE_PREFIX);
  if (!m) return pathname.startsWith("/") ? pathname : `/${pathname}`;
  const rest = pathname.slice(m[0].length) || "/";
  return rest.startsWith("/") ? rest : `/${rest}`;
}

/** Absolute URLs for metadata.alternates — prefer /en|/ru prefixes. */
export function buildLocaleAlternates(
  pathname: string,
  search: string,
): { canonical: string; languages: Record<string, string> } {
  const base = getSiteUrl().replace(/\/$/, "");
  const bare = stripLocalePrefix(pathname);
  const raw = search.startsWith("?") ? search.slice(1) : search;
  const q = new URLSearchParams(raw);
  q.delete("lang");
  const qs = q.toString();
  const suffix = qs ? `?${qs}` : "";
  const ruUrl = `${base}/ru${bare === "/" ? "" : bare}${suffix}`;
  const enUrl = `${base}/en${bare === "/" ? "" : bare}${suffix}`;
  // Canonical follows current path locale if present, else ru
  const m = pathname.match(LOCALE_PREFIX);
  const canonical = m?.[1] === "en" ? enUrl : ruUrl;
  return {
    canonical,
    languages: {
      "ru-RU": ruUrl,
      "en-US": enUrl,
      "x-default": ruUrl,
    },
  };
}
