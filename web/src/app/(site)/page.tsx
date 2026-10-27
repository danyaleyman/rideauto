import type { Metadata } from "next";
import { getSiteUrl } from "@/lib/env";
import { HomeLanding } from "@/components/home/HomeLanding";
import { createT } from "@/lib/i18n";
import { getServerLocale } from "@/lib/locale-server";
import { localeAlternatesMetadata } from "@/lib/site-alternates-metadata";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();
  const t = createT(locale);
  const alt = await localeAlternatesMetadata();
  return {
    title: t("home.meta.title"),
    description: t("home.meta.description"),
    alternates: alt.alternates,
    openGraph: {
      title: t("home.meta.ogTitle"),
      description: t("home.meta.ogDescription"),
      type: "website",
      url: "/",
    },
  };
}

const homeJsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "Ride Auto",
      url: `${getSiteUrl()}/`,
      logo: {
        "@type": "ImageObject",
        url: `${getSiteUrl()}/image/logo%20no%20text.svg`,
      },
    },
    {
      "@type": "WebSite",
      name: "Ride Auto",
      url: `${getSiteUrl()}/`,
      publisher: { "@type": "Organization", name: "Ride Auto" },
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
