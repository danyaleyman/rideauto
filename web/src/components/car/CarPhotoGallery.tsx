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
};

export default function CarPhotoGallery({ images: rawImages, title }: CarPhotoGalleryProps) {
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

  /** Следующие 4 индекса для вертикальной колонки (циклически). */
  const sideSlots = [1, 2, 3, 4].map((k) => (safeActive + k) % n);
  const moreCount = n > 4 ? Math.max(0, n - 4) : 0;

  return (
    <>
      <section className="mt-6 rounded-2xl border border-border bg-card p-3 shadow-sm sm:p-4">
        <div className="grid gap-3 lg:grid-cols-[1fr_92px] lg:items-stretch">
          <div
            className="relative aspect-[16/10] min-h-[200px] cursor-zoom-in overflow-hidden rounded-xl border border-border bg-muted sm:min-h-[280px] lg:aspect-auto lg:min-h-[min(56vh,520px)]"
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
              sizes="(min-width: 1024px) 65vw, 96vw"
              className="object-cover"
              priority
              unoptimized
            />
            {n > 1 ? (
              <div
                className="absolute bottom-3 end-3 flex items-center gap-0.5 rounded-full border border-white/20 bg-black/60 px-1 py-0.5 text-xs text-white shadow-lg backdrop-blur-md"
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

          <div className="flex flex-row gap-2 lg:flex-col lg:justify-between">
            {sideSlots.map((idx, slotI) => {
              const src = images[idx];
              const isLastSlot = slotI === 3;
              const showMore = isLastSlot && moreCount > 0;
              return (
                <button
                  key={`${slotI}-${idx}`}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setActive(idx);
                    openLightbox(idx);
                  }}
                  className={cn(
                    "relative aspect-[4/3] w-[22%] shrink-0 overflow-hidden rounded-lg border-2 border-transparent ring-offset-2 transition-all hover:border-primary/50 lg:aspect-auto lg:h-0 lg:min-h-[72px] lg:w-full lg:flex-1",
                    idx === safeActive && "ring-2 ring-primary",
                  )}
                  aria-label={`Фото ${idx + 1}`}
                >
                  <Image
                    src={src}
                    alt=""
                    fill
                    sizes="96px"
                    className="object-cover"
                    loading="lazy"
                    unoptimized
                  />
                  {showMore ? (
                    <span className="absolute inset-0 flex items-center justify-center bg-black/55 text-sm font-semibold text-white">
                      +{moreCount}
                    </span>
                  ) : null}
                </button>
              );
            })}
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
