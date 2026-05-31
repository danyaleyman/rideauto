"use client";

import Image from "next/image";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { useProxiedCarGalleryUrls } from "@/lib/catalog-image-proxy";
import { imageUrlDedupeKey } from "@/lib/car-gallery-images";
import { isCatalogListedToday } from "@/lib/catalog-listed-today";
import {
  type CarListingAvailability,
  carSourceBadgeVariant,
  carSourceShortRegionLabel,
} from "@/lib/car-listing-trust";
import { useBodyScrollLock } from "@/hooks/use-body-scroll-lock";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type CarPhotoGalleryProps = {
  images: string[];
  title: string;
  sourceKey?: string | null;
  /** ISO created_at каталога — бейдж «Добавлено сегодня», если нет бейджа региона. */
  catalogCreatedAt?: string | null;
  /** Продан / зарезервирован / в продаже — оверлей и доступность галереи. */
  availability?: CarListingAvailability;
};

const THUMB_COUNT = 4;

export default function CarPhotoGallery({
  images: rawImages,
  title,
  sourceKey,
  catalogCreatedAt,
  availability = "available",
}: CarPhotoGalleryProps) {
  const { t } = useLocaleContext();
  const images = useMemo(() => {
    const raw = rawImages.filter((x) => /^https?:\/\//i.test(x.trim()));
    const seen = new Set<string>();
    const out: string[] = [];
    for (const u of raw) {
      const k = imageUrlDedupeKey(u);
      if (seen.has(k)) continue;
      seen.add(k);
      out.push(u.trim());
    }
    return out;
  }, [rawImages]);

  const { thumbUrls, mediumUrls } = useProxiedCarGalleryUrls(images);

  const n = images.length;
  const [active, setActive] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIdx, setLightboxIdx] = useState(0);
  useBodyScrollLock(lightboxOpen);
  const thumbBtnRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const safeActive = n ? Math.min(active, n - 1) : 0;
  const current = mediumUrls[safeActive] ?? "";

  const openLightbox = useCallback((idx: number) => {
    if (!n) return;
    const i = ((idx % n) + n) % n;
    setLightboxIdx(i);
    setLightboxOpen(true);
  }, [n]);

  const go = useCallback(
    (delta: number) => {
      if (!n) return;
      setActive((a) => (a + delta + n) % n);
    },
    [n],
  );

  const goLightbox = useCallback(
    (delta: number) => {
      if (!n) return;
      setLightboxIdx((i) => (i + delta + n) % n);
    },
    [n],
  );

  useEffect(() => {
    if (!lightboxOpen || !n) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        goLightbox(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goLightbox(-1);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setLightboxOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxOpen, n, goLightbox]);

  useEffect(() => {
    if (!lightboxOpen) return;
    const el = thumbBtnRefs.current[lightboxIdx];
    el?.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }, [lightboxOpen, lightboxIdx]);

  if (!n) return null;

  const lightboxMainSrc = mediumUrls[lightboxIdx] ?? "";

  const badgeVariant = carSourceBadgeVariant(sourceKey);
  const showSourceBadge = badgeVariant === "encar" || badgeVariant === "china";
  const showListedTodayBadge = !showSourceBadge && isCatalogListedToday(catalogCreatedAt);

  /** Без дублей: при n=1 старый (active+k+1)%n давал четыре раза индекс 0. */
  const sideCap = n > 1 ? Math.min(THUMB_COUNT, n - 1) : 0;
  const sideSlots = Array.from({ length: sideCap }, (_, k) => (safeActive + 1 + k) % n);
  const moreCount = Math.max(0, n - 1 - sideCap);

  return (
    <>
      <section className="w-full max-w-full overflow-hidden rounded-2xl border border-border/70 bg-muted shadow-md ring-1 ring-elevated-ring sm:rounded-3xl">
        <div
          className={cn(
            "grid min-h-0 min-w-0 gap-2 lg:gap-3",
            sideCap > 0
              ? "lg:grid-cols-[minmax(0,1fr)_clamp(152px,17vw,216px)] lg:items-stretch lg:min-h-[min(58vh,640px)]"
              : "lg:grid-cols-1",
          )}
        >
          <div
            className="relative aspect-[4/3] min-h-[200px] w-full cursor-zoom-in overflow-hidden bg-muted sm:min-h-[240px] lg:aspect-auto lg:min-h-0 lg:h-full"
            onClick={() => openLightbox(safeActive)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openLightbox(safeActive);
              }
            }}
            role="button"
            tabIndex={0}
            aria-label={t("gallery.open")}
          >
            {current ? (
              <Image
                src={current}
                alt={t("gallery.photoAlt", { title, n: safeActive + 1 })}
                fill
                sizes="(min-width: 1536px) 900px, (min-width: 1280px) 75vw, (min-width: 1024px) 72vw, 100vw"
                className="object-cover object-center"
                priority
                fetchPriority="high"
                unoptimized
              />
            ) : (
              <div className="flex size-full items-center justify-center bg-muted">
                <Loader2 className="size-10 animate-spin text-muted-foreground" aria-hidden />
                <span className="sr-only">{t("gallery.loading")}</span>
              </div>
            )}
            {availability === "sold" ? (
              <div className="pointer-events-none absolute inset-0 z-[1] flex items-center justify-center bg-black/58 px-4">
                <p className="text-center text-base font-semibold leading-snug text-white drop-shadow-md sm:text-lg">
                  {t("car.purchase.sold")}
                </p>
              </div>
            ) : availability === "reserved" ? (
              <div className="pointer-events-none absolute inset-0 z-[1] flex items-center justify-center bg-amber-950/55 px-4">
                <p className="text-center text-base font-semibold leading-snug text-amber-50 drop-shadow-md sm:text-lg">
                  {t("gallery.reserved")}
                </p>
              </div>
            ) : null}
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/35 to-transparent"
              aria-hidden
            />

            {badgeVariant === "encar" ? (
              <div className="pointer-events-none absolute start-3 top-3 z-[2] rounded-md bg-red-600 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-white shadow-md">
                {carSourceShortRegionLabel(sourceKey)}
              </div>
            ) : badgeVariant === "china" ? (
              <div className="pointer-events-none absolute start-3 top-3 z-[2] rounded-md bg-sky-700 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-white shadow-md dark:bg-sky-600">
                {carSourceShortRegionLabel(sourceKey)}
              </div>
            ) : showListedTodayBadge ? (
              <div className="pointer-events-none absolute start-3 top-3 z-[2] max-w-[min(100%,14rem)] rounded-md bg-black/60 px-2 py-1 text-[10px] font-medium leading-snug text-white shadow-md ring-1 ring-white/15 backdrop-blur-sm sm:text-[11px]">
                {t("gallery.listedToday")}
              </div>
            ) : null}

            {n > 1 ? (
              <div
                className="absolute bottom-2 end-2 max-w-[calc(100%-1rem)] sm:bottom-3 sm:end-3 flex items-center gap-0.5 rounded-full border border-white/25 bg-black/65 px-1 py-0.5 text-[11px] text-white shadow-lg backdrop-blur-sm sm:text-xs"
                onClick={(e) => e.stopPropagation()}
                role="presentation"
              >
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  className="size-7 rounded-full text-white hover:bg-white/15 hover:text-white"
                  aria-label={t("gallery.prev")}
                  onClick={() => go(-1)}
                >
                  <ChevronLeft className="size-4 rtl:rotate-180" />
                </Button>
                <span className="min-w-[3.25rem] px-1 text-center tabular-nums">
                  {safeActive + 1} / {n}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  className="size-7 rounded-full text-white hover:bg-white/15 hover:text-white"
                  aria-label={t("gallery.next")}
                  onClick={() => go(1)}
                >
                  <ChevronRight className="size-4 rtl:rotate-180" />
                </Button>
              </div>
            ) : null}
          </div>

          {sideCap > 0 ? (
            <div className="flex min-h-0 min-w-0 flex-col bg-transparent lg:h-full">
              <div className="flex max-w-full flex-nowrap gap-2 overflow-x-auto overscroll-x-contain px-1 py-1 [-webkit-overflow-scrolling:touch] [scrollbar-width:thin] lg:h-full lg:min-h-0 lg:flex-1 lg:flex-col lg:gap-2 lg:overflow-hidden lg:px-0 lg:py-0">
                {sideSlots.map((idx, slotI) => {
                  const src = thumbUrls[idx] ?? "";
                  const isLastSlot = slotI === sideSlots.length - 1;
                  const showMore = isLastSlot && moreCount > 0;
                  return (
                    <button
                      key={`${slotI}-${idx}`}
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setActive(idx);
                      }}
                      onDoubleClick={(e) => {
                        e.stopPropagation();
                        openLightbox(idx);
                      }}
                      className={cn(
                        "relative h-[4.25rem] w-[4.75rem] shrink-0 snap-start overflow-hidden rounded-lg border-2 border-transparent bg-transparent transition-all hover:border-primary/50 sm:h-[4.5rem] sm:w-[5.25rem] lg:h-auto lg:min-h-0 lg:w-full lg:flex-1 lg:basis-0 lg:rounded-xl lg:border lg:border-border/40 lg:ring-0 lg:snap-none",
                        idx === safeActive &&
                          "ring-2 ring-primary ring-offset-1 ring-offset-muted lg:ring-2 lg:ring-inset lg:ring-primary/70 lg:ring-offset-0",
                      )}
                      aria-label={
                        showMore
                          ? t("gallery.thumbShowMore", { n: idx + 1, more: moreCount })
                          : t("gallery.thumbShow", { n: idx + 1 })
                      }
                    >
                      {src ? (
                        <Image
                          src={src}
                          alt=""
                          fill
                          sizes="(min-width: 1024px) 200px, 28vw"
                          className="object-cover"
                          loading="lazy"
                          unoptimized
                        />
                      ) : (
                        <div className="size-full animate-pulse bg-muted/90" aria-hidden />
                      )}
                      {showMore ? (
                        <span className="absolute inset-0 flex items-center justify-center bg-black/65 px-1 text-center text-[10px] font-semibold leading-tight text-white sm:text-xs">
                          {t("gallery.morePhotos", { count: moreCount })}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogContent
          showCloseButton={false}
          overlayClassName="bg-black/55 backdrop-blur-md data-closed:backdrop-blur-none"
          className={cn(
            "data-closed:animate-out data-closed:fade-out-0",
            "fixed z-50 flex !h-[100dvh] !max-h-[100dvh] !w-full !max-w-none !translate-x-0 !translate-y-0 flex-col gap-0 !rounded-none border-0 bg-zinc-950 p-0 !shadow-none !ring-0",
            "!inset-0 !top-0 !start-0",
            "data-open:animate-in data-open:fade-in-0 data-open:duration-150",
          )}
        >
          <DialogHeader className="sr-only">
            <DialogTitle>{t("gallery.dialogTitle")}</DialogTitle>
          </DialogHeader>

          <div className="relative flex min-h-0 flex-1 items-center justify-center px-4 pt-4 pb-2 sm:px-10">
            {n > 1 ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-lg"
                className="absolute start-2 top-1/2 z-10 size-12 -translate-y-1/2 rounded-full bg-black/50 text-white hover:bg-black/70 hover:text-white sm:start-6"
                aria-label={t("gallery.prev")}
                onClick={() => goLightbox(-1)}
              >
                <ChevronLeft className="size-7 rtl:rotate-180" aria-hidden />
              </Button>
            ) : null}
            {n > 1 ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-lg"
                className="absolute end-2 top-1/2 z-10 size-12 -translate-y-1/2 rounded-full bg-black/50 text-white hover:bg-black/70 hover:text-white sm:end-6"
                aria-label={t("gallery.next")}
                onClick={() => goLightbox(1)}
              >
                <ChevronRight className="size-7 rtl:rotate-180" aria-hidden />
              </Button>
            ) : null}

            <div className="relative flex max-h-[calc(100dvh-11rem)] w-full max-w-[min(1400px,96vw)] items-center justify-center">
              {lightboxMainSrc ? (
                <Image
                  src={lightboxMainSrc}
                  alt={t("gallery.photoSlide", { title, n: lightboxIdx + 1, total: n })}
                  width={1800}
                  height={1200}
                  className="max-h-[calc(100dvh-11rem)] w-auto max-w-full object-contain"
                  unoptimized
                />
              ) : (
                <div className="flex min-h-[40vh] items-center justify-center">
                  <Loader2 className="size-12 animate-spin text-white/70" aria-hidden />
                  <span className="sr-only">{t("gallery.loading")}</span>
                </div>
              )}
            </div>
          </div>

          <div className="shrink-0 border-t border-white/10 bg-black/85 px-3 py-3 sm:px-6">
            <div className="mx-auto flex max-w-[min(1400px,96vw)] flex-col items-center gap-3">
              <div className="flex items-center justify-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="rounded-full border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                  disabled={n <= 1}
                  onClick={() => goLightbox(-1)}
                  aria-label={t("gallery.prev")}
                >
                  <ChevronLeft className="size-4 rtl:rotate-180" aria-hidden />
                </Button>
                <span className="min-w-[4rem] px-2 text-center text-sm tabular-nums text-white/90">
                  {lightboxIdx + 1} / {n}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="rounded-full border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                  disabled={n <= 1}
                  onClick={() => goLightbox(1)}
                  aria-label={t("gallery.next")}
                >
                  <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="rounded-full border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                  aria-label={t("gallery.close")}
                  onClick={() => setLightboxOpen(false)}
                >
                  <X className="size-4" aria-hidden />
                </Button>
              </div>

              <div className="flex max-w-full gap-2 overflow-x-auto py-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                {thumbUrls.map((src, i) => (
                  <button
                    key={`${images[i]}-${i}`}
                    ref={(el) => {
                      thumbBtnRefs.current[i] = el;
                    }}
                    type="button"
                    onClick={() => setLightboxIdx(i)}
                    className={cn(
                      "relative h-14 w-[5.25rem] shrink-0 overflow-hidden rounded-md border-2 transition-colors sm:h-16 sm:w-24",
                      i === lightboxIdx ? "border-white" : "border-transparent opacity-70 hover:opacity-100",
                    )}
                    aria-label={t("gallery.thumbPhoto", { n: i + 1 })}
                    aria-current={i === lightboxIdx ? "true" : undefined}
                  >
                    {src ? (
                      <Image src={src} alt="" fill className="object-cover" sizes="96px" unoptimized />
                    ) : (
                      <div className="size-full animate-pulse bg-white/10" aria-hidden />
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
