import type { Metadata } from "next";
import { getSiteUrl } from "@/lib/env";
import { HomeLanding } from "@/components/home/HomeLanding";

export const metadata: Metadata = {
  title: "Главная",
  description:
    "Авто из Кореи, Китая и Японии под ключ: каталог, видеоотчёты осмотра, договор и сопровождение до Владивостока. World Ride Auto.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "World Ride Auto — авто из Азии под ключ",
    description:
      "Подбор с площадок и аукционов, проверка, логистика и понятные этапы до вручения.",
    type: "website",
    url: "/",
  },
};

const homeJsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "World Ride Auto",
      url: `${getSiteUrl()}/`,
      logo: {
        "@type": "ImageObject",
        url: `${getSiteUrl()}/image/logo%20no%20text.svg`,
      },
    },
    {
      "@type": "WebSite",
      name: "World Ride Auto",
      url: `${getSiteUrl()}/`,
      publisher: { "@type": "Organization", name: "World Ride Auto" },
    },
  ],
};

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(homeJsonLd) }}
      />
      <HomeLanding />
    </>
  );
}
