"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { HOME_MARKETS } from "@/lib/home-markets";
import { useLocaleContext } from "@/components/LocaleProvider";
import { PhotoPlaceholder } from "@/components/ui/photo-placeholder";

/** Направления (Корея, Китай, США) — статичная сетка карточек. */
export function MarketDirections() {
  const { t } = useLocaleContext();

  return (
    <section className="border-y border-border bg-background py-16 sm:py-24" aria-label={t("home.markets.aria")}>
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
          {t("home.markets.eyebrow")}
        </p>
        <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-4xl lg:text-5xl">
          {t("home.markets.title")}
        </h2>
        <ul className="mt-12 grid list-none gap-6 sm:grid-cols-2 xl:grid-cols-4">
          {HOME_MARKETS.map((market) => {
            const country = t(`home.markets.${market.id}.country`);
            return (
              <li
                key={market.id}
                className="group flex min-w-0 flex-col overflow-hidden rounded-2xl border border-elevated-ring bg-card"
              >
                <PhotoPlaceholder
                  label={t("home.markets.photoSlot", { country })}
                  className="rounded-none border-b border-border"
                />
                <div className="flex flex-1 flex-col p-5">
                  <p className="text-lg font-semibold tracking-tight text-foreground">{country}</p>
                  <ul className="mt-2 flex-1 space-y-1.5 text-sm leading-6 text-muted-foreground">
                    <li>{t(`home.markets.${market.id}.point1`)}</li>
                    <li>{t(`home.markets.${market.id}.point2`)}</li>
                  </ul>
                  {market.catalogDisabled ? (
                    <p className="mt-5 text-sm text-muted-foreground">{t("home.markets.catalogSoon")}</p>
                  ) : (
                    <Link
                      href={market.catalogHref}
                      className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-foreground underline-offset-4 hover:underline"
                    >
                      {t("home.markets.catalogPrefix")} {country}
                      <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />
                    </Link>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
