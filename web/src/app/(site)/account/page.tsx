import type { Metadata } from "next";
import { AccountPageClient } from "@/components/account/AccountPageClient";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = createT(await getServerLocale());
  return {
    title: t("account.title"),
    robots: { index: false, follow: false },
  };
}

export default function AccountPage() {
  return <AccountPageClient />;
}
