import type { Metadata } from "next";
import { AboutEffects } from "@/components/legacy-marketing/AboutEffects";
import { LegacyMarketingPage } from "@/components/legacy-marketing/LegacyMarketingPage";

export const metadata: Metadata = {
  title: "О компании",
  description:
    "World Ride Auto: автомобили из Кореи и Азии, доставка во Владивосток, прозрачные условия и сопровождение сделки.",
  alternates: { canonical: "/about" },
};

export default function AboutPage() {
  return (
    <>
      <LegacyMarketingPage slug="about" />
      <AboutEffects />
    </>
  );
}
