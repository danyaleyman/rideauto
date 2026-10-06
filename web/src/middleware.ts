/** Locale-prefixed URLs + ?lang= + Accept-Language bootstrap. */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  canonicalCatalogQueryString,
  catalogLegacyPathRedirect,
  catalogUrlNeedsCanonicalization,
} from "@/lib/catalog-url-canonical";
import { LOCALE_COOKIE } from "@/lib/locale-constants";

const LOCALE_PREFIX = /^\/(en|ru)(?=\/|$)/;

function stripLocalePrefix(pathname: string): { locale: "en" | "ru" | null; path: string } {
  const m = pathname.match(LOCALE_PREFIX);
  if (!m) return { locale: null, path: pathname };
  const locale = m[1] as "en" | "ru";
  const rest = pathname.slice(m[0].length) || "/";
  return { locale, path: rest.startsWith("/") ? rest : `/${rest}` };
}

function preferAcceptLanguage(header: string | null): "en" | "ru" | null {
  if (!header) return null;
  const lower = header.toLowerCase();
  // First matching tag wins roughly
  if (/(^|,)\s*en\b/.test(lower) && !/(^|,)\s*ru\b/.test(lower.split(",")[0] || "")) {
    // If primary is en
    const primary = lower.split(",")[0]?.trim() || "";
    if (primary.startsWith("en")) return "en";
  }
  if (/(^|,)\s*ru\b/.test(lower)) {
    const primary = lower.split(",")[0]?.trim() || "";
    if (primary.startsWith("ru")) return "ru";
  }
  if (/(^|,)\s*en\b/.test(lower)) return "en";
  return null;
}

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const { locale: pathLocale, path: stripped } = stripLocalePrefix(pathname);

  // Redirect legacy catalog paths (operate on stripped path)
  const legacyPath = catalogLegacyPathRedirect(stripped);
  if (legacyPath) {
    const url = request.nextUrl.clone();
    const prefix = pathLocale ? `/${pathLocale}` : "";
    url.pathname = `${prefix}/catalog`;
    if (legacyPath.market === "china") {
      url.searchParams.set("region", "china");
    } else {
      url.searchParams.delete("region");
    }
    url.searchParams.delete("source");
    return NextResponse.redirect(url, 301);
  }

  if (stripped === "/catalog" || stripped === "/catalog/") {
    if (catalogUrlNeedsCanonicalization(searchParams)) {
      const url = request.nextUrl.clone();
      const prefix = pathLocale ? `/${pathLocale}` : "";
      url.pathname = `${prefix}/catalog`;
      const qs = canonicalCatalogQueryString(searchParams);
      url.search = qs ? `?${qs}` : "";
      return NextResponse.redirect(url, 301);
    }
  }

  // Rewrite /en/... and /ru/... to unprefixed app routes
  let response: NextResponse;
  if (pathLocale) {
    const url = request.nextUrl.clone();
    url.pathname = stripped;
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("x-pathname", pathname);
    requestHeaders.set("x-search", request.nextUrl.search);
    requestHeaders.set("x-locale-prefix", pathLocale);
    response = NextResponse.rewrite(url, {
      request: { headers: requestHeaders },
    });
    response.cookies.set(LOCALE_COOKIE, pathLocale, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
  } else {
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("x-pathname", pathname);
    requestHeaders.set("x-search", request.nextUrl.search);
    response = NextResponse.next({
      request: { headers: requestHeaders },
    });
  }

  const lang = searchParams.get("lang");
  if (lang === "en" || lang === "ru") {
    response.cookies.set(LOCALE_COOKIE, lang, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
  } else if (!request.cookies.get(LOCALE_COOKIE)?.value && !pathLocale) {
    const fromHeader = preferAcceptLanguage(request.headers.get("accept-language"));
    if (fromHeader) {
      response.cookies.set(LOCALE_COOKIE, fromHeader, {
        path: "/",
        maxAge: 60 * 60 * 24 * 365,
        sameSite: "lax",
      });
    }
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
