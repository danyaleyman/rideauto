import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getSiteUrl } from "@/lib/env";

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
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-zinc-200 bg-white px-6 py-10 shadow-sm">
          <p className="text-sm font-medium uppercase tracking-wide text-blue-600">
            World Ride Auto
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl">
            Авто из Южной Кореи и Китая
          </h1>
          <p className="mt-3 max-w-2xl text-base text-zinc-600 sm:text-lg">
            Каталог на Next.js: первая отрисовка с сервера, поиск и фильтры в браузере через FastAPI,
            Meilisearch и PostgreSQL.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link className="inline-flex items-center justify-center rounded-xl bg-blue-700 px-6 py-3 text-center text-sm font-semibold text-white" href="/catalog">
              Открыть каталог
            </Link>
            <Link className="inline-flex items-center justify-center rounded-xl border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-800" href="/buy">
              Как купить
            </Link>
            <a
              className="inline-flex items-center justify-center rounded-xl border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-800"
              href="https://t.me/nikits15"
              target="_blank"
              rel="noopener noreferrer"
            >
              Написать в Telegram
            </a>
          </div>
        </section>

        <section
          className="mt-10 grid gap-4 sm:grid-cols-2"
          aria-label="Выбор рынка каталога"
        >
          <Link
            href="/catalog?region=korea"
            className="flex items-center justify-between gap-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm"
          >
            <span>
              <span className="block text-lg font-semibold text-zinc-900">
                Из Кореи
              </span>
              <span className="mt-1 block text-sm text-zinc-500">
                Фильтры, Encar, расчёт «под ключ»
              </span>
            </span>
            <span className="relative h-14 w-20 shrink-0 overflow-hidden rounded-lg bg-zinc-100">
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
            className="flex items-center justify-between gap-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm"
          >
            <span>
              <span className="block text-lg font-semibold text-zinc-900">
                Из Китая
              </span>
              <span className="mt-1 block text-sm text-zinc-500">
                Dongchedi / Che168, отдельный индекс в поиске
              </span>
            </span>
            <span className="relative h-14 w-20 shrink-0 overflow-hidden rounded-lg bg-zinc-100">
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

        <p className="mt-10 text-center text-sm text-zinc-500">
          Каталог с фильтрами и поиском — в разделе{" "}
          <Link className="font-medium text-blue-600" href="/catalog">
            Каталог
          </Link>
          . SEO-посадки доступны по путям{" "}
          <code className="rounded bg-zinc-100 px-1">/seo/korea/…</code> (статика из
          сборки).
        </p>
      </div>
    </>
  );
}
