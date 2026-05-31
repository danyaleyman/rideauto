"use client";

import { ModelMediaCascade } from "@/components/home/ModelMediaCascade";
import { Button } from "@/components/ui/button";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";
import { HOME_MARKETS, type HomeMarketId } from "@/lib/home-markets";
import { useLocaleContext } from "@/components/LocaleProvider";
import { useGLTF } from "@react-three/drei";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const SWIPE_OFFSET = 56;
const ROTATE_PAUSE_MS = 900;

function marketPoints(t: (path: string) => string, id: HomeMarketId): string[] {
  return [1, 2, 3].map((i) => t(`home.markets.${id}.point${i}`));
}

export function MarketDirectionsCarousel() {
  const { t } = useLocaleContext();
  const reduceMotion = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [pauseAutoRotate, setPauseAutoRotate] = useState(true);
  const market = HOME_MARKETS[index]!;

  const country = t(`home.markets.${market.id}.country`);
  const points = useMemo(() => marketPoints(t, market.id), [t, market.id]);
  const catalogLabel = market.catalogDisabled
    ? t("home.markets.catalogSoon")
    : `${t("home.markets.catalogPrefix")} ${country}`;

  useEffect(() => {
    const { markets } = HOME_LANDING_MEDIA;
    const run = () => {
      useGLTF.preload(markets.korea.model);
      useGLTF.preload(markets.china.model);
      useGLTF.preload(markets.japan.model);
    };
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(run);
      return () => window.cancelIdleCallback(id);
    }
    const id = globalThis.setTimeout(run, 400);
    return () => globalThis.clearTimeout(id);
  }, []);

  useEffect(() => {
    setPauseAutoRotate(true);
    const id = window.setTimeout(() => setPauseAutoRotate(false), ROTATE_PAUSE_MS);
    return () => window.clearTimeout(id);
  }, [market.id]);

  const goTo = useCallback((next: number) => {
    const len = HOME_MARKETS.length;
    setIndex(((next % len) + len) % len);
  }, []);

  const goPrev = useCallback(() => goTo(index - 1), [goTo, index]);
  const goNext = useCallback(() => goTo(index + 1), [goTo, index]);

  const pauseRotate = useCallback(() => {
    setPauseAutoRotate(true);
  }, []);

  const resumeRotateLater = useCallback(() => {
    window.setTimeout(() => setPauseAutoRotate(false), ROTATE_PAUSE_MS);
  }, []);

  return (
    <section className="border-y border-border bg-muted/25 py-16 sm:py-24" aria-label={t("home.markets.aria")}>
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm uppercase tracking-[0.22em] text-muted-foreground">{t("home.markets.eyebrow")}</p>
            <h2 className="mt-3 max-w-xl text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl lg:text-5xl">
              {t("home.markets.title")}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="rounded-full"
              onClick={() => {
                pauseRotate();
                goPrev();
              }}
              aria-label={t("home.markets.prev")}
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              className="rounded-full"
              onClick={() => {
                pauseRotate();
                goNext();
              }}
              aria-label={t("home.markets.next")}
            >
              <ChevronRight className="h-5 w-5" />
            </Button>
          </div>
        </div>

        <motion.div className="mt-10 grid items-center gap-8 lg:grid-cols-2 lg:gap-12">
          <div className="relative bg-transparent">
            <AnimatePresence mode="wait">
              <motion.div
                key={market.id}
                initial={reduceMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={reduceMotion ? undefined : { opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              >
                <ModelMediaCascade
                  media={market.media}
                  autoRotate={!pauseAutoRotate}
                  autoRotateDelayMs={ROTATE_PAUSE_MS}
                />
                <p className="mt-3 text-center text-xs text-muted-foreground">
                  {market.modelLabel}
                  <span className="hidden sm:inline"> · {t("home.markets.rotateDesktop")}</span>
                  <span className="sm:hidden"> · {t("home.markets.rotateMobile")}</span>
                </p>
              </motion.div>
            </AnimatePresence>
          </div>

          <motion.div
            className="min-h-[280px] cursor-grab active:cursor-grabbing"
            drag={reduceMotion ? false : "x"}
            dragConstraints={{ left: 0, right: 0 }}
            dragElastic={0.12}
            onDragStart={pauseRotate}
            onDragEnd={(_, info) => {
              if (info.offset.x < -SWIPE_OFFSET) goNext();
              else if (info.offset.x > SWIPE_OFFSET) goPrev();
              resumeRotateLater();
            }}
          >
            <AnimatePresence mode="wait">
              <motion.div
                key={market.id}
                initial={reduceMotion ? false : { opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={reduceMotion ? undefined : { opacity: 0, x: -16 }}
                transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                className="flex h-full flex-col"
              >
                <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">{t("home.markets.direction")}</p>
                <h3 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-foreground sm:text-4xl">
                  {country}
                </h3>
                <ul className="mt-6 space-y-3">
                  {points.map((point) => (
                    <li key={point} className="flex gap-3 text-base leading-7 text-muted-foreground">
                      <span className="mt-2.5 h-px w-6 shrink-0 bg-foreground/25" aria-hidden />
                      {point}
                    </li>
                  ))}
                </ul>
                <div className="mt-8">
                  {market.catalogDisabled ? (
                    <Button disabled className="rounded-full" type="button">
                      {catalogLabel}
                    </Button>
                  ) : (
                    <Button asChild className="rounded-full">
                      <Link href={market.catalogHref}>{catalogLabel}</Link>
                    </Button>
                  )}
                </div>
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </motion.div>

        <div className="mt-8 flex justify-center gap-2" role="tablist" aria-label={t("home.markets.tabsAria")}>
          {HOME_MARKETS.map((item, i) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={i === index}
              aria-label={t(`home.markets.${item.id}.country`)}
              onClick={() => {
                pauseRotate();
                setIndex(i);
              }}
              className={`h-2 rounded-full transition-all ${
                i === index ? "w-8 bg-foreground" : "w-2 bg-foreground/25 hover:bg-foreground/40"
              }`}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
