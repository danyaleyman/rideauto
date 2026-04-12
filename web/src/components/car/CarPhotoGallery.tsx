"use client";

import Image from "next/image";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { imageUrlDedupeKey } from "@/lib/car-gallery-images";
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
};

const THUMB_COUNT = 4;

export default function CarPhotoGallery({
  images: rawImages,
  title,
  sourceKey,
}: CarPhotoGalleryProps) {
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

  const n = images.length;
  const [active, setActive] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIdx, setLightboxIdx] = useState(0);
  const thumbBtnRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const safeActive = n ? Math.min(active, n - 1) : 0;
  const current = images[safeActive] ?? "";

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

  if (!n || !current) return null;

  const srcNorm = (sourceKey ?? "").toLowerCase();
  const showEncarBadge = srcNorm === "encar";

  /** Без дублей: при n=1 старый (active+k+1)%n давал четыре раза индекс 0. */
  const sideCap = n > 1 ? Math.min(THUMB_COUNT, n - 1) : 0;
  const sideSlots = Array.from({ length: sideCap }, (_, k) => (safeActive + 1 + k) % n);
  const moreCount = Math.max(0, n - 1 - sideCap);

  return (
    <>
      <section className="w-full max-w-full overflow-hidden rounded-2xl border border-border/70 bg-card shadow-md ring-1 ring-black/[0.05] dark:ring-white/[0.06] sm:rounded-3xl">
        <div
          className={cn(
            "grid min-w-0 gap-0 lg:items-stretch",
            sideCap > 0 ? "lg:grid-cols-[minmax(0,1fr)_160px]" : "lg:grid-cols-1",
          )}
        >
          <div
            className="relative aspect-[16/10] min-h-[200px] cursor-zoom-in overflow-hidden bg-muted sm:min-h-[260px] lg:aspect-auto lg:min-h-[min(58vh,560px)]"
            onClick={() => openLightbox(safeActive)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openLightbox(safeActive);
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Открыть галерею фото"
          >
            <Image
              src={current}
              alt={`${title} — фото ${safeActive + 1}`}
              fill
              sizes="(min-width: 1024px) 72vw, 100vw"
              className="object-cover object-center"
              priority
              unoptimized
            />
            <div
              className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/35 to-transparent"
              aria-hidden
            />

            {showEncarBadge ? (
              <div className="pointer-events-none absolute start-3 top-3 rounded-md bg-red-600 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-white shadow-md">
                Encar
              </div>
            ) : (
              <div className="pointer-events-none absolute start-3 top-3 rounded-md bg-foreground/85 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-background shadow-md">
                WRA
              </div>
            )}

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
                  aria-label="Предыдущее фото"
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
                  aria-label="Следующее фото"
                  onClick={() => go(1)}
                >
                  <ChevronRight className="size-4 rtl:rotate-180" />
                </Button>
              </div>
            ) : null}
          </div>

          {sideCap > 0 ? (
            <div className="min-w-0 border-t border-border/50 lg:flex lg:flex-col lg:border-s lg:border-t-0">
              <p className="mb-0 hidden px-2 pt-2 text-center text-[10px] font-medium uppercase tracking-wider text-muted-foreground lg:mb-1 lg:block lg:px-2 lg:pt-3">
                Ещё фото
              </p>
              <div className="flex max-w-full flex-nowrap gap-2 overflow-x-auto overscroll-x-contain px-2 py-2 [-webkit-overflow-scrolling:touch] [scrollbar-width:thin] lg:flex-col lg:gap-2.5 lg:overflow-visible lg:px-2 lg:py-3">
                {sideSlots.map((idx, slotI) => {
                  const src = images[idx];
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
                        "relative aspect-[4/3] h-[4.25rem] w-[4.75rem] shrink-0 snap-start overflow-hidden rounded-lg border-2 border-transparent transition-all hover:border-primary/50 sm:h-[4.75rem] sm:w-[5.25rem] lg:aspect-auto lg:h-0 lg:min-h-[88px] lg:w-full lg:flex-1 lg:snap-none",
                        idx === safeActive &&
                          "ring-2 ring-primary ring-offset-1 ring-offset-background lg:ring-offset-2",
                      )}
                      aria-label={`Показать фото ${idx + 1}`}
                    >
                      <Image
                        src={src}
                        alt=""
                        fill
                        sizes="(min-width: 1024px) 148px, 28vw"
                        className="object-cover"
                        loading="lazy"
                        unoptimized
                      />
                      {showMore ? (
                        <span className="absolute inset-0 flex items-center justify-center bg-black/60 text-sm font-bold text-white">
                          +{moreCount}
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
            <DialogTitle>Галерея фото</DialogTitle>
          </DialogHeader>

          <div className="relative flex min-h-0 flex-1 items-center justify-center px-4 pt-4 pb-2 sm:px-10">
            {n > 1 ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-lg"
                className="absolute start-2 top-1/2 z-10 size-12 -translate-y-1/2 rounded-full bg-black/50 text-white hover:bg-black/70 hover:text-white sm:start-6"
                aria-label="Назад"
                onClick={() => goLightbox(-1)}
              >
                <ChevronLeft className="size-7 rtl:rotate-180" />
              </Button>
            ) : null}
            {n > 1 ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-lg"
                className="absolute end-2 top-1/2 z-10 size-12 -translate-y-1/2 rounded-full bg-black/50 text-white hover:bg-black/70 hover:text-white sm:end-6"
                aria-label="Вперёд"
                onClick={() => goLightbox(1)}
              >
                <ChevronRight className="size-7 rtl:rotate-180" />
              </Button>
            ) : null}

            <div className="relative flex max-h-[calc(100dvh-11rem)] w-full max-w-[min(1400px,96vw)] items-center justify-center">
              <Image
                src={images[lightboxIdx] ?? current}
                alt={`${title} — ${lightboxIdx + 1} из ${n}`}
                width={1800}
                height={1200}
                className="max-h-[calc(100dvh-11rem)] w-auto max-w-full object-contain"
                unoptimized
              />
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
                  aria-label="Предыдущее"
                >
                  <ChevronLeft className="size-4 rtl:rotate-180" />
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
                  aria-label="Следующее"
                >
                  <ChevronRight className="size-4 rtl:rotate-180" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="rounded-full border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                  aria-label="Закрыть"
                  onClick={() => setLightboxOpen(false)}
                >
                  <X className="size-4" />
                </Button>
              </div>

              <div className="flex max-w-full gap-2 overflow-x-auto py-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
                {images.map((src, i) => (
                  <button
                    key={`${src}-${i}`}
                    ref={(el) => {
                      thumbBtnRefs.current[i] = el;
                    }}
                    type="button"
                    onClick={() => setLightboxIdx(i)}
                    className={cn(
                      "relative h-14 w-[5.25rem] shrink-0 overflow-hidden rounded-md border-2 transition-colors sm:h-16 sm:w-24",
                      i === lightboxIdx ? "border-white" : "border-transparent opacity-70 hover:opacity-100",
                    )}
                    aria-label={`Фото ${i + 1}`}
                    aria-current={i === lightboxIdx ? "true" : undefined}
                  >
                    <Image src={src} alt="" fill className="object-cover" sizes="96px" unoptimized />
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
