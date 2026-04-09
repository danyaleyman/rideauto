import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getSiteUrl } from "@/lib/env";
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
          <section className="rounded-2xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-black/[0.03] backdrop-blur-sm dark:ring-white/[0.06] sm:rounded-3xl sm:p-6 lg:p-8">
            <p className="text-sm font-medium uppercase tracking-wide text-primary">World Ride Auto</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground [overflow-wrap:anywhere] sm:text-3xl lg:text-4xl">
              Авто из Южной Кореи и Китая
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground [overflow-wrap:anywhere] sm:text-lg">
              Каталог на Next.js: первая отрисовка с сервера, поиск и фильтры в браузере через FastAPI,
              Meilisearch и PostgreSQL.
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

          <section
            className="mt-8 grid min-w-0 gap-3 sm:mt-10 sm:grid-cols-2 sm:gap-4"
            aria-label="Выбор рынка каталога"
          >
            <Link
              href="/catalog?region=korea"
              className="flex min-w-0 items-center justify-between gap-3 rounded-2xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-black/[0.03] transition-shadow hover:shadow-md dark:ring-white/[0.06] sm:gap-4 sm:rounded-3xl sm:p-5"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-base font-semibold text-foreground [overflow-wrap:anywhere] sm:text-lg">
                  Из Кореи
                </span>
                <span className="mt-1 block text-sm leading-snug text-muted-foreground [overflow-wrap:anywhere]">
                  Фильтры, Encar, расчёт «под ключ»
                </span>
              </span>
              <span className="relative h-14 w-20 shrink-0 overflow-hidden rounded-lg bg-muted">
                <Image
                  src="/image/korea-market.png"
                  alt=""
                  fill
                  className="object-cover"
                  sizes="80px"
                />
              </span>
            </Link>
            <Link
              href="/catalog?region=china"
              className="flex min-w-0 items-center justify-between gap-3 rounded-2xl border border-border/50 bg-card/70 p-4 shadow-sm ring-1 ring-black/[0.03] transition-shadow hover:shadow-md dark:ring-white/[0.06] sm:gap-4 sm:rounded-3xl sm:p-5"
            >
              <span className="min-w-0 flex-1">
                <span className="block text-base font-semibold text-foreground [overflow-wrap:anywhere] sm:text-lg">
                  Из Китая
                </span>
                <span className="mt-1 block text-sm leading-snug text-muted-foreground [overflow-wrap:anywhere]">
                  Dongchedi / Che168, отдельный индекс в поиске
                </span>
              </span>
              <span className="relative h-14 w-20 shrink-0 overflow-hidden rounded-lg bg-muted">
                <Image
                  src="/image/china-market.png"
                  alt=""
                  fill
                  className="object-cover"
                  sizes="80px"
                />
              </span>
            </Link>
          </section>

          <p className="mt-8 text-center text-sm leading-relaxed text-muted-foreground [overflow-wrap:anywhere] sm:mt-10">
            Каталог с фильтрами и поиском — в разделе{" "}
            <Link className="font-medium text-primary underline-offset-4 hover:underline" href="/catalog">
              Каталог
            </Link>
            . SEO-посадки доступны по путям{" "}
            <code className="break-all rounded-md bg-muted px-1.5 py-0.5 text-xs text-foreground">
              /seo/korea/…
            </code>{" "}
            (статика из сборки).
          </p>
        </div>
      </div>
    </>
  );
}
