"use client";

import Image from "next/image";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
  /** Для бейджа в углу (напр. encar — «осмотр на площадке»). */
  sourceKey?: string | null;
};

const THUMB_COUNT = 4;

export default function CarPhotoGallery({
  images: rawImages,
  title,
  sourceKey,
}: CarPhotoGalleryProps) {
  const images = useMemo(
    () => rawImages.filter((x) => /^https?:\/\//i.test(x.trim())),
    [rawImages],
  );
  const n = images.length;
  const [active, setActive] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIdx, setLightboxIdx] = useState(0);

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
      setActive((a) => {
        const next = (a + delta + n) % n;
        return next;
      });
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
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightboxOpen, n, goLightbox]);

  if (!n || !current) return null;

  const srcNorm = (sourceKey ?? "").toLowerCase();
  const showEncarBadge = srcNorm === "encar";

  const sideSlots = Array.from({ length: THUMB_COUNT }, (_, k) => (safeActive + k + 1) % n);
  const moreCount = n > THUMB_COUNT ? Math.max(0, n - THUMB_COUNT) : 0;

  return (
    <>
      <section className="w-full overflow-hidden rounded-2xl border border-border/80 bg-card shadow-lg ring-1 ring-black/5 dark:ring-white/10">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_118px] lg:items-stretch">
          <div
            className="relative aspect-[16/10] min-h-[220px] cursor-zoom-in overflow-hidden bg-muted sm:min-h-[300px] lg:aspect-auto lg:min-h-[min(58vh,560px)]"
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
                className="absolute bottom-3 end-3 flex items-center gap-0.5 rounded-full border border-white/25 bg-black/65 px-1 py-0.5 text-xs text-white shadow-lg backdrop-blur-sm"
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

          <div className="flex flex-row gap-0 border-t border-border/60 bg-muted/25 p-2 lg:flex-col lg:border-s lg:border-t-0 lg:p-2">
            <p className="mb-2 hidden text-center text-[10px] font-medium uppercase tracking-wider text-muted-foreground lg:block">
              Ещё фото
            </p>
            <div className="flex flex-1 flex-row gap-2 lg:flex lg:flex-col lg:gap-2">
              {sideSlots.map((idx, slotI) => {
                const src = images[idx];
                const isLastSlot = slotI === THUMB_COUNT - 1;
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
                      "relative aspect-[4/3] w-[23%] shrink-0 overflow-hidden rounded-lg border-2 border-transparent transition-all hover:border-primary/40 lg:aspect-auto lg:h-0 lg:min-h-[76px] lg:w-full lg:flex-1",
                      idx === safeActive && "ring-2 ring-primary ring-offset-1 ring-offset-background",
                    )}
                    aria-label={`Показать фото ${idx + 1}`}
                  >
                    <Image
                      src={src}
                      alt=""
                      fill
                      sizes="120px"
                      className="object-cover"
                      loading="lazy"
                      unoptimized
                    />
                    {showMore ? (
                      <span className="absolute inset-0 flex items-center justify-center bg-black/60 text-xs font-bold text-white">
                        +{moreCount}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogContent
          showCloseButton={false}
          className="max-h-[96vh] max-w-[min(1200px,96vw)] gap-0 border-0 bg-zinc-950 p-0 shadow-2xl ring-1 ring-white/10"
        >
          <DialogHeader className="sr-only">
            <DialogTitle>Галерея фото</DialogTitle>
          </DialogHeader>
          <div className="relative flex max-h-[85vh] items-center justify-center bg-black">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="absolute top-2 end-2 z-20 rounded-full bg-black/50 text-white hover:bg-black/70 hover:text-white"
              aria-label="Закрыть"
              onClick={() => setLightboxOpen(false)}
            >
              <X className="size-5" />
            </Button>
            {n > 1 ? (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-lg"
                  className="absolute start-2 z-10 size-12 rounded-full bg-black/45 text-white hover:bg-black/65 hover:text-white"
                  aria-label="Назад"
                  onClick={() => goLightbox(-1)}
                >
                  <ChevronLeft className="size-7 rtl:rotate-180" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-lg"
                  className="absolute end-2 z-10 size-12 rounded-full bg-black/45 text-white hover:bg-black/65 hover:text-white"
                  aria-label="Вперёд"
                  onClick={() => goLightbox(1)}
                >
                  <ChevronRight className="size-7 rtl:rotate-180" />
                </Button>
              </>
            ) : null}
            <div className="relative flex h-[min(80vh,820px)] w-full items-center justify-center p-4">
              <Image
                src={images[lightboxIdx] ?? current}
                alt={`${title} — ${lightboxIdx + 1} из ${n}`}
                width={1600}
                height={1200}
                className="max-h-full max-w-full object-contain"
                unoptimized
              />
            </div>
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/65 px-4 py-1.5 text-sm tabular-nums text-white backdrop-blur-sm">
              {lightboxIdx + 1} / {n}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
