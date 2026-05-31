import type { Metadata } from "next";
import { PrivacyPageContent } from "@/components/legal/PrivacyPageContent";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = createT(await getServerLocale());
  return {
    title: t("legal.privacy.metaTitle"),
    description: t("legal.privacy.metaDescription"),
    alternates: { canonical: "/privacy" },
  };
}

export default function PrivacyPage() {
  return <PrivacyPageContent />;
}
