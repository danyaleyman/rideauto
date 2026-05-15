"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, ChevronDown } from "lucide-react";
import { useRef } from "react";

const HERO_IMAGE = "/assets/landing-main-page.png";

const TRUST = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"];

export function HomeLanding() {
  const heroRef = useRef(null);

  // GLOBAL scroll (без container — стабильнее)
  const { scrollYProgress, scrollY } = useScroll();

  const heroY = useTransform(scrollY, [0, 600], [0, 120]);
  const heroScale = useTransform(scrollY, [0, 600], [1.15, 1]);
  const heroOpacity = useTransform(scrollY, [0, 400], [1, 0.85]);

  const bounceAnimation = {
    y: [0, -10, 0, -6, 0],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut" as const,
    },
  };

  const scrollToNext = () => {
    const next = document.getElementById("scene-2");
    next?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="relative">

      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* SCROLL INDICATOR */}
      <motion.div
        animate={bounceAnimation}
        onClick={scrollToNext}
        className="fixed bottom-6 left-1/2 z-40 hidden -translate-x-1/2 cursor-pointer rounded-full bg-background/80 p-2 backdrop-blur sm:block"
      >
        <ChevronDown className="h-6 w-6 text-foreground" />
      </motion.div>

      {/* ================= HERO ================= */}
      <section className="relative flex min-h-screen items-center overflow-hidden px-4 sm:px-6">

        {/* BACKGROUND GLOW */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 right-[-10%] h-[600px] w-[600px] rounded-full bg-primary/20 blur-[160px]" />
          <div className="absolute bottom-[-30%] left-[-10%] h-[600px] w-[600px] rounded-full bg-blue-500/10 blur-[180px]" />
        </div>

        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-10 lg:grid-cols-2">

          {/* TEXT */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="max-w-xl"
          >
            <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
              Ride Auto
            </p>

            <h1 className="mt-6 text-4xl font-semibold leading-[1.05] sm:text-5xl lg:text-7xl">
              Автомобили из Азии
              <br />
              как новый стандарт
            </h1>

            <p className="mt-6 text-muted-foreground sm:text-lg">
              Подбор, проверка и доставка автомобилей без посредников.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg" className="rounded-full px-8">
                <Link href="/catalog">Смотреть каталог</Link>
              </Button>

              <Button asChild size="lg" variant="secondary" className="rounded-full px-8">
                <Link href="/contacts">Обсудить подбор</Link>
              </Button>
            </div>

            <div className="mt-10 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
              {TRUST.map((t) => (
                <span key={t} className="transition-colors hover:text-foreground">
                  {t}
                </span>
              ))}
            </div>
          </motion.div>

          {/* IMAGE (FIXED + BIGGER) */}
          <motion.div
            ref={heroRef}
            style={{ y: heroY, scale: heroScale, opacity: heroOpacity }}
            className="relative flex justify-center lg:justify-end"
          >
            <div className="absolute inset-0 scale-125 bg-primary/10 blur-[160px]" />

            <Image
              src={HERO_IMAGE}
              alt="Hero car"
              width={2000}
              height={1400}
              priority
              className="
                relative z-10
                w-[130%] sm:w-[120%] lg:w-[150%]
                max-w-none
                object-contain
                drop-shadow-[0_80px_180px_rgba(0,0,0,0.35)]
              "
            />
          </motion.div>

        </div>
      </section>

      {/* ================= SCENE 2 ================= */}
      <section
        id="scene-2"
        className="flex min-h-screen items-center justify-center px-6"
      >
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          className="mx-auto max-w-4xl text-center"
        >
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
            Контроль качества
          </p>

          <h2 className="mt-6 text-3xl font-semibold sm:text-5xl">
            Вы принимаете решение
            <br />
            только после проверки
          </h2>

          <p className="mt-6 text-muted-foreground sm:text-lg">
            Фото, видео и техническая диагностика автомобиля до покупки.
          </p>

          <Link
            href="/reports"
            className="group mt-10 inline-flex items-center gap-2 text-primary hover:underline"
          >
            Примеры отчётов
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </motion.div>
      </section>

      {/* ================= SCENE 3 ================= */}
      <section className="flex min-h-screen items-center px-6">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="mx-auto w-full max-w-6xl"
        >
          <div className="relative overflow-hidden rounded-[40px] border bg-muted shadow-xl">
            <Image
              src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
              alt="Inspection"
              width={1800}
              height={1000}
              className="object-cover transition-transform duration-700 hover:scale-[1.03]"
            />
          </div>
        </motion.div>
      </section>

      {/* ================= SCENE 4 ================= */}
      <section className="flex min-h-screen items-center px-6">
        <div className="mx-auto w-full max-w-6xl">
          <motion.h2
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-3xl font-semibold sm:text-5xl"
          >
            Как проходит покупка
          </motion.h2>

          <div className="mt-16 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["01", "Подбор", "Ищем авто под запрос"],
              ["02", "Проверка", "Видео и диагностика"],
              ["03", "Выкуп", "Сделка и документы"],
              ["04", "Доставка", "Передача клиенту"],
            ].map(([n, t, d], i) => (
              <motion.div
                key={n}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
              >
                <div className="text-6xl text-muted-foreground/20">{n}</div>
                <h3 className="mt-4 text-xl font-medium">{t}</h3>
                <p className="mt-2 text-muted-foreground">{d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= CTA ================= */}
      <section className="flex min-h-screen items-center bg-primary px-6 text-primary-foreground">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl sm:text-5xl">
            Найдём автомобиль,
            <br />
            который вам подходит
          </h2>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild size="lg" className="rounded-full bg-white text-primary">
              <Link href="/catalog">Подобрать авто</Link>
            </Button>

            <Button asChild size="lg" variant="secondary" className="rounded-full">
              <a href="https://t.me/nikits15" target="_blank">
                Telegram
              </a>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}