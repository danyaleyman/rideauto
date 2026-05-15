"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { useRef } from "react";

const HERO_IMAGE = "/assets/landing-main-page.png";

const TRUST = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"];

export function HomeLanding() {
  const heroRef = useRef(null);

  const { scrollYProgress, scrollY } = useScroll();

  // cinematic parallax system
  const heroY = useTransform(scrollY, [0, 700], [0, 120]);
  const heroScale = useTransform(scrollY, [0, 700], [1.18, 1]);

  return (
    <div className="relative">

      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* ================= HERO ================= */}
      <section className="relative min-h-screen flex items-center px-5 sm:px-6 overflow-hidden">

        {/* background glow layers */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 right-[-15%] h-[700px] w-[700px] rounded-full bg-primary/20 blur-[180px]" />
          <div className="absolute bottom-[-35%] left-[-15%] h-[700px] w-[700px] rounded-full bg-blue-500/10 blur-[200px]" />
        </div>

        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 lg:grid-cols-2 items-center gap-10">

          {/* TEXT */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="
              relative z-20
              max-w-xl
              lg:pr-12
            "
          >
            <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
              Ride Auto
            </p>

            {/* FIX 2: cleaned typography (no broken stacking feel) */}
            <h1 className="mt-6 text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-semibold leading-[1.05]">
              Автомобили из Азии
              <span className="block text-muted-foreground/70 font-normal mt-2">
                как новый стандарт
              </span>
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
                <span key={t} className="hover:text-foreground transition-colors">
                  {t}
                </span>
              ))}
            </div>
          </motion.div>

          {/* IMAGE (FIX: +15–20% visual scale) */}
          <motion.div
            ref={heroRef}
            style={{ y: heroY, scale: heroScale }}
            className="
              relative
              flex justify-center lg:justify-end
              z-10
            "
          >
            <div className="absolute inset-0 scale-125 bg-primary/10 blur-[160px]" />

            <Image
              src={HERO_IMAGE}
              alt="Hero car"
              width={2200}
              height={1500}
              priority
              className="
                relative z-10
                w-full
                max-w-[1050px] lg:max-w-[1250px] xl:max-w-[1350px]
                object-contain
                drop-shadow-[0_90px_200px_rgba(0,0,0,0.35)]
              "
            />
          </motion.div>

        </div>
      </section>

      {/* ================= SCENE 2 ================= */}
      <section className="flex min-h-screen items-center justify-center px-6 py-28">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          className="text-center max-w-4xl"
        >
          <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
            Контроль качества
          </p>

          <h2 className="mt-6 text-3xl sm:text-5xl font-semibold">
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
          </Link>
        </motion.div>
      </section>

      {/* ================= SCENE 3 ================= */}
      <section className="flex min-h-screen items-center px-6 py-28">
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="mx-auto w-full max-w-6xl"
        >
          <div className="relative overflow-hidden rounded-[40px] border shadow-xl bg-muted">
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

      {/* ================= SCENE 4 ================= */}
      <section className="flex min-h-screen items-center px-6 py-28">
        <div className="mx-auto w-full max-w-6xl">
          <h2 className="text-3xl sm:text-5xl font-semibold">
            Как проходит покупка
          </h2>

          <div className="mt-16 grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["01", "Подбор", "Ищем авто под запрос"],
              ["02", "Проверка", "Видео и диагностика"],
              ["03", "Выкуп", "Сделка и документы"],
              ["04", "Доставка", "Передача клиенту"],
            ].map(([n, t, d]) => (
              <div key={n}>
                <div className="text-6xl text-muted-foreground/20">{n}</div>
                <h3 className="mt-4 text-xl font-medium">{t}</h3>
                <p className="mt-2 text-muted-foreground">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= CTA (FIXED THEME BUG) ================= */}
      <section className="flex min-h-screen items-center bg-primary text-primary-foreground px-6">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl sm:text-5xl font-semibold">
            Найдём автомобиль,
            <br />
            который вам подходит
          </h2>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild size="lg" className="rounded-full bg-white text-primary">
              <Link href="/catalog">Подобрать авто</Link>
            </Button>

            <Button asChild size="lg" variant="secondary" className="rounded-full">
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