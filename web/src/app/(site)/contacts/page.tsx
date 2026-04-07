import type { Metadata } from "next";
import { LegacyMarketingPage } from "@/components/legacy-marketing/LegacyMarketingPage";

export const metadata: Metadata = {
  title: "Контакты",
  description:
    "Связь с World Ride Auto: Telegram, ВКонтакте, Авито. Подбор авто из Кореи и Китая.",
  alternates: { canonical: "/contacts" },
};

export default function ContactsPage() {
  return <LegacyMarketingPage slug="contacts" wrapClassName="contacts-wrap" />;
}
