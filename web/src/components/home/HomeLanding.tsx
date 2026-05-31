"use client";

import dynamic from "next/dynamic";
import { ModelMediaCascade } from "@/components/home/ModelMediaCascade";
import { type ReactNode, useMemo } from "react";
import { motion, useReducedMotion, useScroll } from "framer-motion";
import "@/lib/preload-landing-models";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";
import { useLocaleContext } from "@/components/LocaleProvider";

const LOGO = "WORLD RIDE AUTO";
const TELEGRAM_CHANNEL = "https://t.me/worldrideauto";
const DOCS_URL = "https://disk.yandex.ru/d/WxPQ4fBr7k6e_Q";
const INSPECTION_URL = "https://disk.yandex.ru/d/RYB3Xyk8sNQUZQ";
const HANDOVER_URL =
  "https://www.instagram.com/reel/DV6iYb2iJsf/?utm_source=ig_web_button_share_sheet&igsh=MzRlODBiNWFlZA==";

const linkClass =
  "font-medium text-foreground underline decoration-foreground/40 underline-offset-4 transition-colors hover:decoration-foreground";

const MarketDirectionsCarousel = dynamic(
  () =>
    import("@/components/home/MarketDirectionsCarousel").then((m) => m.MarketDirectionsCarousel),
  {
    ssr: false,
    loading: () => (
      <section className="border-y border-border bg-muted/25 py-16 sm:py-24" aria-hidden>
        <div className="mx-auto h-[480px] max-w-[1440px] animate-pulse px-4 sm:px-6 lg:px-10" />
      </section>
    ),
  },
);

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
      whileHover={{ y: -1 }}
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
  const { scrollYProgress } = useScroll();

  const processSteps = useMemo((): ProcessStep[] => {
    return [
      {
        n: "01",
        title: t("home.landing.step01Title"),
        body: (
          <>
            {t("home.landing.step01Body")}{" "}
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className={linkClass}>
              {t("home.landing.step01Contract")}
            </a>{" "}
            {t("home.landing.step01Joiner")}{" "}
            <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" className={linkClass}>
              {t("home.landing.step01Estimate")}
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
      {
        n: "06",
        title: t("home.landing.step06Title"),
        body: (
          <Link
            href="/buy"
            className="mt-2 inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            {t("home.landing.step06Body")}
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        ),
      },
    ];
  }, [t]);

  return (
    <div className="relative isolate overflow-x-hidden bg-background text-foreground">
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-px w-full origin-left bg-foreground/25"
        aria-hidden
      />

      <section className="relative flex min-h-[calc(100dvh-4rem)] items-center overflow-hidden bg-background py-12 sm:py-16 lg:min-h-[100dvh] lg:py-20">
        <div className="relative z-10 mx-auto grid w-full max-w-[1440px] items-center gap-8 px-4 sm:px-6 lg:grid-cols-[1fr_1.05fr] lg:items-center lg:gap-12 lg:px-10">
          <motion.div
            className="lg:py-4"
            initial={reduceMotion ? false : { opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="inline-flex items-center gap-3 rounded-full border border-brand/25 bg-brand/5 px-4 py-2 text-caption uppercase tracking-[0.28em] text-brand">
              <span className="h-px w-8 bg-brand/35" />
              {LOGO}
            </div>

            <h1 className="mt-6 max-w-xl text-[2rem] font-semibold leading-[1.08] tracking-[-0.04em] text-foreground sm:mt-7 sm:max-w-lg sm:text-4xl lg:text-[2.75rem] lg:leading-[1.06]">
              {t("home.landing.heroTitle")}
            </h1>

            <p className="mt-5 max-w-lg text-base leading-7 text-muted-foreground sm:mt-6 sm:text-lg sm:leading-8">
              {t("home.landing.heroLead")}
            </p>

            <div className="mt-8 flex flex-wrap gap-3 sm:mt-9">
              <LandingButton href="/catalog" className="bg-primary text-primary-foreground hover:bg-primary/90">
                {t("home.landing.catalogCta")}
              </LandingButton>
              <LandingButton
                href={TELEGRAM_CHANNEL}
                external
                className="border border-border bg-background text-foreground hover:bg-muted"
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

      <MarketDirectionsCarousel />

      <section id="company" className="bg-background py-16 sm:py-24" aria-label={t("home.landing.processAria")}>
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
          <motion.h2
            className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-foreground sm:text-5xl lg:text-6xl"
            initial={reduceMotion ? false : { opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            {t("home.landing.processTitle")}
          </motion.h2>
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {processSteps.map((step, i) => (
              <motion.div
                key={step.n}
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="min-h-[220px] rounded-2xl border border-border bg-card p-5 shadow-sm"
              >
                <div className="text-5xl font-semibold tracking-[-0.06em] text-muted-foreground/30" aria-hidden>
                  {step.n}
                </div>
                <div className="mt-10 text-xl font-semibold text-foreground">{step.title}</div>
                <div className="mt-3 text-sm leading-6 text-muted-foreground">{step.body}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border bg-muted/25 py-20 sm:py-28">
        <motion.div
          className="mx-auto max-w-3xl px-4 text-center sm:px-6"
          initial={reduceMotion ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl lg:text-5xl">
            {t("home.landing.ctaTitle")}
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
            {t("home.landing.ctaLead")}
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <LandingButton href="/catalog" className="bg-foreground text-background hover:bg-foreground/90">
              {t("home.landing.ctaCatalog")}
            </LandingButton>
            <LandingButton
              href={TELEGRAM_CHANNEL}
              external
              className="border border-border bg-background text-foreground hover:bg-muted"
            >
              {t("home.landing.telegramCta")}
            </LandingButton>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
