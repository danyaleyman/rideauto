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

const CAR = "/assets/landing-main-page.png";

export function HomeLanding() {
  const ref = useRef(null);

  const { scrollYProgress, scrollY } = useScroll();

  const progress = useSpring(scrollYProgress, {
    stiffness: 110,
    damping: 28,
  });

  /**
   * =========================
   * KEYNOTE CAMERA SYSTEM
   * =========================
   * wide → medium → detail → fade
   */

  // HERO (wide cinematic shot)
  const heroScale = useTransform(scrollY, [0, 800], [1.25, 1]);
  const heroY = useTransform(scrollY, [0, 800], [0, 120]);

  // PROOF (slight zoom stabilization)
  const proofOpacity = useTransform(scrollY, [500, 1000], [0, 1]);

  // ENGINEERING DETAIL (focus shift)
  const engineeringOpacity = useTransform(scrollY, [900, 1500], [0, 1]);

  // PROCESS (clean presentation fade-in)
  const processOpacity = useTransform(scrollY, [1300, 1900], [0, 1]);

  return (
    <div ref={ref} className="relative bg-background">

      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: progress }}
        className="fixed top-0 left-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* ================= HERO (WIDE SHOT) ================= */}
      <section className="relative min-h-screen flex items-center overflow-hidden">

        {/* studio lighting */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 right-[-25%] h-[900px] w-[900px] rounded-full bg-primary/20 blur-[240px]" />
          <div className="absolute bottom-[-30%] left-[-25%] h-[900px] w-[900px] rounded-full bg-blue-500/10 blur-[260px]" />
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-background/40" />
        </div>

        {/* CAR (hero object) */}
        <motion.div
          style={{ scale: heroScale, y: heroY }}
          className="absolute inset-0 flex items-center justify-center"
        >
          <div className="w-full max-w-[1500px]">
            <Image
              src={CAR}
              alt="car"
              width={2600}
              height={1600}
              priority
              className="w-full object-contain drop-shadow-[0_180px_320px_rgba(0,0,0,0.45)]"
            />
          </div>
        </motion.div>

        {/* HERO TEXT (minimal keynote style) */}
        <div className="absolute left-6 top-24 max-w-xl">
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
            Ride Auto Presentation
          </p>

          <h1 className="mt-6 text-4xl sm:text-6xl lg:text-7xl font-semibold leading-[1.05]">
            Автомобили из Азии
          </h1>

          <p className="mt-3 text-2xl text-muted-foreground">
            новый стандарт качества
          </p>
        </div>

      </section>

      {/* ================= PROOF SECTION ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">
        <motion.div
          style={{ opacity: proofOpacity }}
          className="mx-auto max-w-4xl text-center"
        >
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
            Контроль качества
          </p>

          <h2 className="mt-6 text-3xl sm:text-5xl font-semibold">
            Каждое авто проходит
            полную проверку
          </h2>

          <p className="mt-6 text-muted-foreground sm:text-lg">
            Фото, видео, диагностика и технический отчёт до сделки.
          </p>

          <Link href="/reports" className="mt-6 inline-block text-primary">
            Смотреть отчёты →
          </Link>
        </motion.div>
      </section>

      {/* ================= ENGINEERING VISUAL ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">
        <motion.div
          style={{ opacity: engineeringOpacity }}
          className="mx-auto max-w-6xl w-full"
        >
          <div className="overflow-hidden rounded-[40px] border shadow-xl">
            <Image
              src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
              alt="inspection"
              width={1800}
              height={1000}
              className="object-cover"
            />
          </div>
        </motion.div>
      </section>

      {/* ================= PROCESS ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">
        <motion.div
          style={{ opacity: processOpacity }}
          className="mx-auto max-w-6xl"
        >
          <h2 className="text-3xl sm:text-5xl font-semibold">
            Как проходит покупка
          </h2>

          <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["01", "Подбор", "Анализ рынка"],
              ["02", "Проверка", "Диагностика"],
              ["03", "Выкуп", "Сделка"],
              ["04", "Доставка", "Передача"],
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

      {/* ================= FINAL CTA (LOCKED CONTRAST FIX) ================= */}
      <section className="min-h-screen flex items-center px-5 sm:px-6">

        {/* hard lock surface */}
        <div className="absolute inset-0 bg-black" />

        <div className="relative mx-auto max-w-3xl text-center text-white">
          <h2 className="text-3xl sm:text-5xl font-semibold">
            Найдём автомобиль,
            который вам подходит
          </h2>

          <p className="mt-5 text-white/70">
            Подбор • Проверка • Доставка без посредников
          </p>

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