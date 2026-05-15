"use client";

import {
  motion,
  useScroll,
  useTransform,
} from "framer-motion";

import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useRef } from "react";

const HERO_IMAGE = "/assets/landing-main-page.png";

const TRUST = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"];

export function HomeLanding() {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({ container: containerRef });

  /**
   * 🎬 CLEAN MOTION LAYER (NO SPRINGS)
   */
  const heroScale = useTransform(scrollYProgress, [0, 0.25], [1.1, 1]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.2], [1, 0.9]);

  return (
    <div className="bg-background text-foreground">

      {/* PROGRESS BAR (clean, no spring jitter) */}
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed top-0 left-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* SINGLE SCROLL ENGINE */}
      <div
        ref={containerRef}
        className="
          h-screen overflow-y-scroll
          snap-y snap-proximity
          scroll-smooth
        "
      >

        {/* ================= HERO ================= */}
        <section className="min-h-screen snap-start flex items-center">

          <div className="mx-auto grid w-full max-w-7xl grid-cols-1 lg:grid-cols-2 items-center px-6 lg:px-12 gap-10">

            {/* IMAGE (mobile-first order enforced) */}
            <motion.div
              style={{ scale: heroScale, opacity: heroOpacity }}
              className="
                order-1 lg:order-2
                flex justify-center lg:justify-end
              "
            >
              <Image
                src={HERO_IMAGE}
                alt="car"
                width={2400}
                height={1600}
                priority
                className="
                  w-[120%] lg:w-[150%]
                  object-contain
                  drop-shadow-[0_120px_240px_rgba(0,0,0,0.35)]
                "
              />
            </motion.div>

            {/* TEXT */}
            <div className="order-2 lg:order-1 max-w-xl">

              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Ride Auto
              </p>

              <h1 className="mt-6 text-5xl lg:text-7xl font-semibold leading-[1.05]">
                Автомобили из Азии
              </h1>

              <p className="mt-3 text-xl lg:text-2xl text-muted-foreground">
                как новый стандарт качества
              </p>

              <p className="mt-6 text-muted-foreground">
                Подбор, проверка и доставка автомобилей без посредников
              </p>

              <div className="mt-8 flex gap-3 flex-wrap">
                <Button asChild className="rounded-full px-8">
                  <Link href="/catalog">Каталог</Link>
                </Button>

                <Button asChild variant="secondary" className="rounded-full px-8">
                  <Link href="/contacts">Обсудить</Link>
                </Button>
              </div>

              <div className="mt-10 flex flex-wrap gap-4 text-sm text-muted-foreground">
                {TRUST.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>

            </div>

          </div>

        </section>

        {/* ================= PROOF ================= */}
        <section className="min-h-screen snap-start flex items-center bg-muted/30">

          <div className="mx-auto max-w-6xl grid lg:grid-cols-2 gap-12 items-center px-6">

            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Контроль качества
              </p>

              <h2 className="mt-6 text-4xl lg:text-6xl font-semibold">
                Проверка до покупки
              </h2>

              <p className="mt-6 text-muted-foreground">
                Каждый автомобиль проходит фото, видео и технический аудит
              </p>
            </div>

            <div className="overflow-hidden rounded-3xl border bg-background">
              <Image
                src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
                alt="inspection"
                width={1800}
                height={1000}
                className="object-cover"
              />
            </div>

          </div>

        </section>

        {/* ================= SOURCE ================= */}
        <section className="min-h-screen snap-start flex items-center">

          <div className="mx-auto max-w-6xl grid lg:grid-cols-2 gap-12 items-center px-6">

            <div className="overflow-hidden rounded-3xl border">
              <Image
                src="https://images.unsplash.com/photo-1619767886558-efdc259cde1a?auto=format&fit=crop&w=1800&q=80"
                alt="auction"
                width={1800}
                height={1000}
                className="object-cover"
              />
            </div>

            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Источник авто
              </p>

              <h2 className="mt-6 text-4xl lg:text-6xl font-semibold">
                Прямой доступ к аукционам
              </h2>

              <p className="mt-6 text-muted-foreground">
                Работаем без посредников и скрытых наценок
              </p>
            </div>

          </div>

        </section>

        {/* ================= PROCESS ================= */}
        <section className="min-h-screen snap-start flex items-center">

          <div className="mx-auto max-w-6xl px-6">

            <h2 className="text-4xl lg:text-6xl font-semibold">
              Процесс
            </h2>

            <div className="mt-14 grid grid-cols-2 lg:grid-cols-4 gap-10">
              {[
                ["01", "Подбор"],
                ["02", "Проверка"],
                ["03", "Выкуп"],
                ["04", "Доставка"],
              ].map(([n, t]) => (
                <div key={n}>
                  <div className="text-5xl text-muted-foreground/20">{n}</div>
                  <div className="mt-3 text-xl">{t}</div>
                </div>
              ))}
            </div>

          </div>

        </section>

        {/* ================= CTA ================= */}
        <section className="min-h-screen snap-start flex items-center bg-black text-white">

          <div className="mx-auto max-w-3xl text-center px-6">

            <h2 className="text-4xl lg:text-6xl font-semibold">
              Найдём автомобиль под вас
            </h2>

            <p className="mt-6 text-white/60">
              Полный цикл под ключ — без посредников
            </p>

            <div className="mt-10 flex justify-center gap-3">
              <Button asChild className="rounded-full bg-white text-black">
                <Link href="/catalog">Подобрать авто</Link>
              </Button>

              <Button asChild className="rounded-full border border-white/20 bg-white/5 text-white">
                <a href="https://t.me/nikits15">Telegram</a>
              </Button>
            </div>

          </div>

        </section>

      </div>
    </div>
  );
}