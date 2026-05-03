import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { LOCALE_COOKIE } from "@/lib/locale-constants";

/** Задаёт локаль через ``?lang=en`` / ``?lang=ru`` (cookie на год). Префикс маршрута ``/en`` не используется — см. docs/I18N_ROUTING.md. */
export function middleware(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-pathname", request.nextUrl.pathname);
  requestHeaders.set("x-search", request.nextUrl.search);
  const res = NextResponse.next({
    request: { headers: requestHeaders },
  });
  const lang = request.nextUrl.searchParams.get("lang");
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
