import { catalogPathSegmentToMarket } from "@/lib/catalog-market";
import { parseCatalogUrl, stateToBrowserUrl, type CatalogUrlState } from "@/lib/catalog-url";

/** Нужен ли 301/replace: в query есть legacy ``source`` или лишний ``region=korea``. */
export function catalogUrlNeedsCanonicalization(sp: URLSearchParams): boolean {
  if (sp.has("source")) return true;
  const region = (sp.get("region") || "").toLowerCase();
  if (region === "korea" || region === "encar") return true;
  return false;
}

export function canonicalCatalogQueryString(sp: URLSearchParams): string {
  return stateToBrowserUrl(parseCatalogUrl(sp));
}

/** Канонический query для каталога (без source / encar / che168). */
export function canonicalCatalogSearchParams(sp: URLSearchParams): URLSearchParams {
  const qs = canonicalCatalogQueryString(sp);
  return new URLSearchParams(qs);
}

/** Путь вида /catalog/encar → market для редиректа. */
export function catalogLegacyPathRedirect(pathname: string): { market: CatalogUrlState["market"] } | null {
  const m = pathname.match(/^\/catalog\/([^/]+)\/?$/);
  if (!m) return null;
  const market = catalogPathSegmentToMarket(m[1]);
  if (!market) return null;
  return { market };
}
