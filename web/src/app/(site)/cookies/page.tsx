import type { Metadata } from "next";
import { CookiesPageContent } from "@/components/legal/CookiesPageContent";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = createT(await getServerLocale());
  return {
    title: t("legal.cookies.metaTitle"),
    description: t("legal.cookies.metaDescription"),
    alternates: { canonical: "/cookies" },
  };
}

export default function CookiesPage() {
  return <CookiesPageContent />;
}
