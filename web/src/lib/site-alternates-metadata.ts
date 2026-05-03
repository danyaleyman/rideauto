import type { Metadata } from "next";
import { headers } from "next/headers";
import { buildLocaleAlternates } from "@/lib/hreflang";

/** Читает ``x-pathname`` / ``x-search`` из middleware — для ``generateMetadata`` в layout. */
export async function localeAlternatesMetadata(): Promise<Pick<Metadata, "alternates">> {
  const h = await headers();
  const pathname = h.get("x-pathname") || "/";
  const search = h.get("x-search") ?? "";
  const { canonical, languages } = buildLocaleAlternates(pathname, search);
  return {
    alternates: {
      canonical,
      languages,
    },
  };
}
