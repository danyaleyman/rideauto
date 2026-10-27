"use client";

import { ModelMediaCascade } from "@/components/home/ModelMediaCascade";
import { MarketDirections } from "@/components/home/MarketDirectionsCarousel";
import { HomeTrustStrip } from "@/components/home/HomeTrustStrip";
import { PhotoPlaceholder } from "@/components/ui/photo-placeholder";
import { type ReactNode, useMemo } from "react";
import { motion, useReducedMotion } from "framer-motion";
import "@/lib/preload-landing-models";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";
import { useLocaleContext } from "@/components/LocaleProvider";

const LOGO = "Ride Auto";
const TELEGRAM_CHANNEL = "https://t.me/worldrideauto";
const DOCS_URL = "https://disk.yandex.ru/d/WxPQ4fBr7k6e_Q";
const INSPECTION_URL = "https://disk.yandex.ru/d/RYB3Xyk8sNQUZQ";
const HANDOVER_URL =
  "https://www.instagram.com/reel/DV6iYb2iJsf/?utm_source=ig_web_button_share_sheet&igsh=MzRlODBiNWFlZA==";

const linkClass =
  "font-medium text-foreground underline decoration-foreground/40 underline-offset-4 transition-colors hover:decoration-foreground";

type ProcessStep = {
  n: string;
  title: string;
  body: ReactNode;
};

function LandingButton({
  children,
  className = "",
  href,
  external,
}: {
  children: ReactNode;
  className?: string;
  href: string;
  external?: boolean;
}) {
  return (
    <motion.div
      className="inline-flex"
      whileTap={{ scale: 0.99 }}
      transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
    >
      <Button asChild className={`h-12 rounded-full px-7 text-sm font-semibold ${className}`}>
        {external ? (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ) : (
          <Link href={href}>{children}</Link>
        )}
      </Button>
    </motion.div>
  );
}

export function HomeLanding() {
  const { t } = useLocaleContext();
  const reduceMotion = useReducedMotion();

  const processSteps = useMemo((): ProcessStep[] => {
    return [
      {
        n: "01",
        title: t("home.landing.step01Title"),
        body: (
          <>
            {t("home.landing.step01Body")}{" "}
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className={linkClass}>
              {t("home.landing.contractEstimate")}
            </a>
            .
          </>
        ),
      },
      {
        n: "02",
        title: t("home.landing.step02Title"),
        body: t("home.landing.step02Body"),
      },
      {
        n: "03",
        title: t("home.landing.step03Title"),
        body: (
          <>
            {t("home.landing.step03Body")}{" "}
            <a
              href={INSPECTION_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={`${linkClass} mt-2 inline-flex items-center gap-1`}
            >
              {t("home.landing.step03Link")}
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </a>
          </>
        ),
      },
      {
        n: "04",
        title: t("home.landing.step04Title"),
        body: t("home.landing.step04Body"),
      },
      {
        n: "05",
        title: t("home.landing.step05Title"),
        body: (
          <>
            {t("home.landing.step05Body")}{" "}
            <a
              href={HANDOVER_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={`${linkClass} mt-2 inline-flex items-center gap-1`}
            >
              {t("home.landing.step05Link")}
              <ArrowRight className="h-3.5 w-3.5" aria-hidden />
            </a>
          </>
        ),
      },
    ];
  }, [t]);

  return (
    <div className="relative isolate overflow-x-hidden bg-background text-foreground">
      <section className="relative flex items-center overflow-hidden bg-background py-10 sm:py-14 lg:min-h-[min(720px,calc(100dvh-3.5rem))] lg:py-16">
        {/* Деликатное фоновое свечение — нейтрально, без кричащих цветов. */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-28 right-[-8%] hidden h-[460px] w-[600px] rounded-full bg-brand/5 blur-3xl sm:block"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 left-[-12%] hidden h-[400px] w-[460px] rounded-full bg-muted/70 blur-3xl lg:block"
        />
        <div className="relative z-10 mx-auto grid w-full max-w-[1440px] items-center gap-8 px-4 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:items-center lg:gap-12 lg:px-10">
          <motion.div
            className="lg:py-4"
            initial={reduceMotion ? false : { opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground/80">{LOGO}</p>

            <h1 className="mt-5 max-w-2xl text-[2.125rem] font-semibold leading-[1.06] tracking-[-0.035em] text-foreground sm:mt-6 sm:text-[2.75rem] sm:leading-[1.04] lg:text-[3.25rem] lg:leading-[1.03]">
              {t("home.landing.heroTitle")}
            </h1>

            <p className="mt-5 max-w-xl text-base leading-7 text-muted-foreground/90 sm:mt-6 sm:text-lg sm:leading-8">
              {t("home.landing.heroLead")}
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3 sm:mt-10">
              <LandingButton
                href="/catalog"
                className="gap-2 bg-primary text-primary-foreground shadow-[0_12px_28px_-18px_rgb(0_0_0/0.55)] hover:bg-primary/90"
              >
                {t("home.landing.catalogCta")}
                <ArrowRight className="size-4" aria-hidden />
              </LandingButton>
              <LandingButton
                href={TELEGRAM_CHANNEL}
                external
                className="border border-border/80 bg-background/60 text-foreground/80 hover:bg-muted/60 hover:text-foreground"
              >
                {t("home.landing.telegramCta")}
              </LandingButton>
            </div>
          </motion.div>

          <div className="order-first w-full lg:order-none">
            <ModelMediaCascade
              media={HOME_LANDING_MEDIA.hero}
              autoRotate={false}
              priorityImage
              fallbackDelayMs={7000}
            />
          </div>
        </div>
      </section>

      <HomeTrustStrip />

      <MarketDirections />

      <section id="company" className="bg-background py-16 sm:py-24" aria-label={t("home.landing.processAria")}>
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
          <motion.h2
            className="max-w-3xl text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-4xl lg:text-5xl"
            initial={reduceMotion ? false : { opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            {t("home.landing.processTitle")}
          </motion.h2>
          <div className="mt-12 grid gap-x-10 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {processSteps.map((step, i) => (
              <motion.div
                key={step.n}
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="border-t border-border pt-6"
              >
                <PhotoPlaceholder
                  label={t("home.landing.photoSlot", { step: step.title })}
                  className="mb-6 rounded-xl border border-border/70"
                />
                <div className="text-sm font-medium tabular-nums text-muted-foreground" aria-hidden>
                  {step.n}
                </div>
                <h3 className="mt-3 text-lg font-semibold tracking-tight text-foreground">{step.title}</h3>
                <div className="mt-2 text-sm leading-6 text-muted-foreground">{step.body}</div>
              </motion.div>
            ))}
          </div>
          <div className="mt-12 flex justify-center">
            <LandingButton
              href="/buy"
              className="gap-2 border border-border bg-background text-foreground hover:bg-muted"
            >
              {t("home.landing.processMore")}
              <ArrowRight className="size-4" aria-hidden />
            </LandingButton>
          </div>
        </div>
      </section>

      <section className="border-t border-border bg-muted/40 py-20 sm:py-28">
        <motion.div
          className="mx-auto max-w-3xl px-4 text-center sm:px-6"
          initial={reduceMotion ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-4xl lg:text-5xl">
            {t("home.landing.ctaTitle")}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
            {t("home.landing.ctaLead")}
          </p>
          <dl className="mx-auto mt-12 grid max-w-xl grid-cols-3 gap-x-4 gap-y-6 border-y border-border py-8 sm:gap-x-6">
            {(
              [
                ["home.landing.statCatalogValue", "home.landing.statCatalogLabel"],
                ["home.landing.statMarketsValue", "home.landing.statMarketsLabel"],
                ["home.landing.statTermValue", "home.landing.statTermLabel"],
              ] as const
            ).map(([valueKey, labelKey]) => (
              <div key={labelKey} className="flex min-w-0 flex-col">
                <dt className="order-2 mt-1.5 text-xs leading-5 text-muted-foreground sm:text-sm">
                  {t(labelKey)}
                </dt>
                <dd className="order-1 text-2xl font-semibold tabular-nums tracking-tight text-foreground sm:text-3xl">
                  {t(valueKey)}
                </dd>
              </div>
            ))}
          </dl>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <LandingButton
              href="/catalog"
              className="gap-2 bg-foreground text-background shadow-[0_12px_28px_-18px_rgb(0_0_0/0.5)] hover:bg-foreground/90"
            >
              {t("home.landing.ctaCatalog")}
              <ArrowRight className="size-4" aria-hidden />
            </LandingButton>
            <LandingButton
              href={TELEGRAM_CHANNEL}
              external
              className="border border-border/80 bg-background text-foreground/80 hover:bg-muted/60 hover:text-foreground"
            >
              {t("home.landing.telegramCta")}
            </LandingButton>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
