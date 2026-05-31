import type { Metadata } from "next";
import { AdminLeadsClient } from "@/components/admin/AdminLeadsClient";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";

export async function generateMetadata(): Promise<Metadata> {
  const t = createT(await getServerLocale());
  return {
    title: t("admin.leadsPageTitle"),
    robots: { index: false, follow: false },
  };
}

export default function AdminLeadsPage() {
  return <AdminLeadsClient />;
}
