import type { Metadata } from "next";
import { AgreementPageContent } from "@/components/legal/AgreementPageContent";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = createT(await getServerLocale());
  return {
    title: t("legal.agreement.metaTitle"),
    description: t("legal.agreement.metaDescription"),
    alternates: { canonical: "/agreement" },
  };
}

export default function AgreementPage() {
  return <AgreementPageContent />;
}
