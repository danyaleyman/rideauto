import type { Metadata } from "next";
import Link from "next/link";
import { getSiteUrl } from "@/lib/env";
import { HomeTrustStrip } from "@/components/home/HomeTrustStrip";
import { MotionFadeUp } from "@/components/ui/motion";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Главная",
  description:
    "Автомобили из Кореи и Азии с доставкой во Владивосток. Каталог, фильтры, цены и оформление через World Ride Auto.",
  alternates: { canonical: "/" },
  openGraph: {
    title: "World Ride Auto — авто из Азии",
    description:
      "Каталог автомобилей с Кореи и Китая: цены, комплектации, доставка.",
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
      <div className="min-h-screen overflow-x-hidden bg-gradient-to-b from-muted/40 via-background to-background pb-10 pt-2 sm:pt-4">
        <div className="relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10">
          <MotionFadeUp>
            <section className="rounded-2xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-elevated-ring backdrop-blur-sm sm:rounded-3xl sm:p-6 lg:p-8">
              <p className="text-sm font-medium uppercase tracking-wide text-primary">World Ride Auto</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground [overflow-wrap:anywhere] sm:text-3xl lg:text-4xl">
                Авто из Южной Кореи и Китая
              </h1>
              <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground [overflow-wrap:anywhere] sm:text-lg">
                Подбор, проверка и доставка автомобилей из Азии во Владивосток: актуальные объявления, фильтры и
                понятные шаги до вручения.
              </p>
              <div className="mt-6 flex min-w-0 flex-col gap-3 sm:flex-row sm:flex-wrap">
                <Button className="w-full rounded-xl shadow-sm sm:w-auto" size="lg" asChild>
                  <Link href="/catalog">Открыть каталог</Link>
                </Button>
                <Button variant="outline" className="w-full rounded-xl shadow-sm sm:w-auto" size="lg" asChild>
                  <Link href="/buy">Как купить</Link>
                </Button>
                <Button variant="outline" className="w-full rounded-xl shadow-sm sm:w-auto" size="lg" asChild>
                  <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                    Написать в Telegram
                  </a>
                </Button>
              </div>
            </section>
          </MotionFadeUp>

          <HomeTrustStrip />

          <p className="mt-8 text-center text-sm leading-relaxed text-muted-foreground [overflow-wrap:anywhere] sm:mt-10">
            Каталог с фильтрами и поиском — в разделе{" "}
            <Link className="font-medium text-primary underline-offset-4 hover:underline" href="/catalog">
              Каталог
            </Link>
            . Дополнительные страницы по маркам — в разделе{" "}
            <code className="break-all rounded-md bg-muted px-1.5 py-0.5 text-xs text-foreground">
              /seo/korea/…
            </code>
            .
          </p>
        </div>
      </div>
    </>
  );
}
