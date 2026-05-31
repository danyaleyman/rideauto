import type { Metadata } from "next";
import { BuyPageContent } from "@/components/buy/BuyPageContent";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = createT(await getServerLocale());
  return {
    title: t("buy.pageTitle"),
    description: t("buy.pageDescription"),
    alternates: { canonical: "/buy" },
  };
}

export default function BuyPage() {
  return <BuyPageContent />;
}
