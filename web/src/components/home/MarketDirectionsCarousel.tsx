"use client";

import Link from "next/link";
import { HOME_MARKETS } from "@/lib/home-markets";
import { useLocaleContext } from "@/components/LocaleProvider";
import { PhotoPlaceholder } from "@/components/ui/photo-placeholder";

export function MarketDirectionsCarousel() {
  const { t } = useLocaleContext();

  return (
    <section className="border-y border-border bg-background py-16 sm:py-24" aria-label={t("home.markets.aria")}>
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          {t("home.markets.eyebrow")}
        </p>
        <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl lg:text-5xl">
          {t("home.markets.title")}
        </h2>
        <ul className="mt-10 grid list-none gap-8 sm:grid-cols-2 xl:grid-cols-4">
          {HOME_MARKETS.map((market) => {
            const country = t(`home.markets.${market.id}.country`);
            return (
              <li key={market.id} className="min-w-0">
                <PhotoPlaceholder
                  label={t("home.markets.photoSlot", { country })}
                  className="rounded-none"
                />
                <p className="mt-4 text-lg font-semibold tracking-tight text-foreground">{country}</p>
                <ul className="mt-2 space-y-1.5 text-sm leading-6 text-muted-foreground">
                  <li>{t(`home.markets.${market.id}.point1`)}</li>
                  <li>{t(`home.markets.${market.id}.point2`)}</li>
                </ul>
                {market.catalogDisabled ? (
                  <p className="mt-4 text-sm text-muted-foreground">{t("home.markets.catalogSoon")}</p>
                ) : (
                  <Link
                    href={market.catalogHref}
                    className="mt-4 inline-block text-sm font-medium text-foreground underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground"
                  >
                    {t("home.markets.catalogPrefix")} {country}
                  </Link>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
