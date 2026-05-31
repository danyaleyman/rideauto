import type { Metadata } from "next";
import { ContactsPageClient } from "@/components/contacts/ContactsPageClient";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";
import { localeAlternatesMetadata } from "@/lib/site-alternates-metadata";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();
  const t = createT(locale);
  const alt = await localeAlternatesMetadata();
  return {
    title: t("contacts.title"),
    description: t("contacts.lead"),
    alternates: { canonical: "/contacts", ...alt.alternates },
  };
}

export default function ContactsPage() {
  return <ContactsPageClient />;
}
