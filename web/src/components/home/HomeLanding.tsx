"use client";

import {
  motion,
  useScroll,
  useTransform,
  useSpring,
} from "framer-motion";

import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useRef } from "react";

const HERO_IMAGE = "/assets/landing-main-page.png";

const TRUST = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"];

export function HomeLanding() {
  const containerRef = useRef(null);

  const { scrollYProgress, scrollY } = useScroll();

  // smooth camera
  const smooth = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
  });

  /**
   * =========================
   * CINEMATIC CAMERA SYSTEM
   * =========================
   */

  // HERO: zoom in → settle
  const heroScale = useTransform(scrollY, [0, 800], [1.25, 1]);
  const heroY = useTransform(scrollY, [0, 800], [0, 120]);

  // SCENE DEPTH SHIFT
  const scene2Y = useTransform(scrollY, [400, 1200], [80, 0]);
  const scene2Opacity = useTransform(scrollY, [300, 800], [0, 1]);

  const scene3Scale = useTransform(scrollY, [800, 1500], [0.95, 1]);
  const scene4Opacity = useTransform(scrollY, [1200, 1800], [0, 1]);

  return (
    <div ref={containerRef} className="relative bg-background">

      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: smooth }}
        className="fixed top-0 left-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* ================= HERO (PINNED FEEL) ================= */}
      <section className="relative h-screen flex items-center overflow-hidden">

        {/* cinematic background */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 right-[-20%] h-[800px] w-[800px] rounded-full bg-primary/20 blur-[200px]" />
          <div className="absolute bottom-[-30%] left-[-20%] h-[800px] w-[800px] rounded-full bg-blue-500/10 blur-[220px]" />
        </div>

        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 lg:grid-cols-2 items-center px-5 sm:px-6 gap-10">

          {/* TEXT */}
          <div className="relative z-20 max-w-xl">
            <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
              Ride Auto
            </p>

            <h1 className="mt-5 text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-semibold leading-[1.05]">
              Автомобили из Азии
            </h1>

            <p className="mt-2 text-2xl sm:text-3xl text-muted-foreground">
              как новый стандарт
            </p>

            <p className="mt-5 text-muted-foreground sm:text-lg">
              Подбор, проверка и доставка автомобилей без посредников.
            </p>

            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild size="lg" className="rounded-full px-8">
                <Link href="/catalog">Каталог</Link>
              </Button>

              <Button asChild size="lg" variant="secondary" className="rounded-full px-8">
                <Link href="/contacts">Связаться</Link>
              </Button>
            </div>

            <div className="mt-8 flex flex-wrap gap-4 text-sm text-muted-foreground">
              {TRUST.map((t) => (
                <span key={t}>{t}</span>
              ))}
            </div>
          </div>

          {/* HERO CAR (cinematic camera) */}
          <motion.div
            style={{ scale: heroScale, y: heroY }}
            className="relative flex justify-center lg:justify-end"
          >
            <div className="absolute inset-0 scale-125 bg-primary/10 blur-[180px]" />

            <Image
              src={HERO_IMAGE}
              alt="Hero car"
              width={2400}
              height={1600}
              priority
              className="
                w-full
                max-w-[1200px] lg:max-w-[1400px]
                object-contain
                drop-shadow-[0_120px_240px_rgba(0,0,0,0.35)]
              "
            />
          </motion.div>

        </div>
      </section>

      {/* ================= SCENE 2 (fade in layer) ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">
        <motion.div
          style={{ opacity: scene2Opacity, y: scene2Y }}
          className="mx-auto max-w-4xl text-center"
        >
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
            Контроль качества
          </p>

          <h2 className="mt-5 text-3xl sm:text-5xl font-semibold">
            Вы принимаете решение
            только после проверки
          </h2>

          <p className="mt-5 text-muted-foreground sm:text-lg">
            Фото, видео и техническая диагностика автомобиля до покупки.
          </p>

          <Link href="/reports" className="mt-6 inline-block text-primary">
            Примеры отчётов →
          </Link>
        </motion.div>
      </section>

      {/* ================= SCENE 3 (parallax card) ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">
        <motion.div
          style={{ scale: scene3Scale }}
          className="mx-auto max-w-6xl w-full"
        >
          <div className="overflow-hidden rounded-[40px] border shadow-xl bg-muted">
            <Image
              src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
              alt="Inspection"
              width={1800}
              height={1000}
              className="object-cover hover:scale-[1.03] transition-transform duration-700"
            />
          </div>
        </motion.div>
      </section>

      {/* ================= SCENE 4 (fade up) ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">
        <motion.div
          style={{ opacity: scene4Opacity }}
          className="mx-auto max-w-6xl"
        >
          <h2 className="text-3xl sm:text-5xl font-semibold">
            Как проходит покупка
          </h2>

          <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["01", "Подбор", "Ищем авто под запрос"],
              ["02", "Проверка", "Видео и диагностика"],
              ["03", "Выкуп", "Сделка и документы"],
              ["04", "Доставка", "Передача клиенту"],
            ].map(([n, t, d]) => (
              <div key={n}>
                <div className="text-5xl text-muted-foreground/20">{n}</div>
                <h3 className="mt-3 text-xl font-medium">{t}</h3>
                <p className="mt-2 text-muted-foreground">{d}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </section>

      {/* ================= CTA (FIXED + NO THEME BUG) ================= */}
      <section className="relative min-h-screen flex items-center px-5 sm:px-6">

        {/* hard contrast layer */}
        <div className="absolute inset-0 bg-black dark:bg-primary" />

        <div className="relative mx-auto max-w-3xl text-center text-white">
          <h2 className="text-3xl sm:text-5xl font-semibold">
            Найдём автомобиль,
            который вам подходит
          </h2>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild size="lg" className="rounded-full bg-white text-black">
              <Link href="/catalog">Подобрать авто</Link>
            </Button>

            <Button asChild size="lg" className="rounded-full border border-white/30 bg-white/10 text-white backdrop-blur">
              <a href="https://t.me/nikits15" target="_blank" rel="noreferrer">
                Telegram
              </a>
            </Button>
          </div>
        </div>

      </section>

    </div>
  );
}