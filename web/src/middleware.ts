import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  canonicalCatalogQueryString,
  catalogLegacyPathRedirect,
  catalogUrlNeedsCanonicalization,
} from "@/lib/catalog-url-canonical";
import { LOCALE_COOKIE } from "@/lib/locale-constants";

/** Задаёт локаль через ``?lang=en`` / ``?lang=ru`` (cookie на год). */
export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;

  const legacyPath = catalogLegacyPathRedirect(pathname);
  if (legacyPath) {
    const url = request.nextUrl.clone();
    url.pathname = "/catalog";
    if (legacyPath.market === "china") {
      url.searchParams.set("region", "china");
    } else {
      url.searchParams.delete("region");
    }
    url.searchParams.delete("source");
    return NextResponse.redirect(url, 301);
  }

  if (pathname === "/catalog" || pathname === "/catalog/") {
    if (catalogUrlNeedsCanonicalization(searchParams)) {
      const url = request.nextUrl.clone();
      const qs = canonicalCatalogQueryString(searchParams);
      url.search = qs ? `?${qs}` : "";
      return NextResponse.redirect(url, 301);
    }
  }

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-pathname", pathname);
  requestHeaders.set("x-search", request.nextUrl.search);
  const res = NextResponse.next({
    request: { headers: requestHeaders },
  });
  const lang = searchParams.get("lang");
  if (lang === "en" || lang === "ru") {
    res.cookies.set(LOCALE_COOKIE, lang, {
      path: "/",
      maxAge: 60 * 60 * 24 * 365,
      sameSite: "lax",
    });
  }
  return res;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
