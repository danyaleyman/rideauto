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
  const { scrollYProgress } = useScroll();
  const { scrollY } = useScroll();

  const heroY = useTransform(scrollY, [0, 500], [0, 150]);
  const heroScale = useTransform(scrollY, [0, 500], [1, 0.95]);
  const heroOpacity = useTransform(scrollY, [0, 300], [1, 0.7]);

  return (
    <div>
      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      <div className="snap-y snap-mandatory overflow-y-scroll h-screen">

        {/* ================= HERO (TESLA SCENE 1) ================= */}
        <section ref={heroRef} className="relative flex min-h-screen items-center snap-start overflow-hidden">

          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -top-40 right-[-10%] h-[600px] w-[600px] rounded-full bg-primary/20 blur-[160px]" />
            <div className="absolute bottom-[-30%] left-[-10%] h-[600px] w-[600px] rounded-full bg-blue-500/10 blur-[180px]" />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-background" />
          </div>

          <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-16 px-6 lg:grid-cols-[1.05fr_1fr]">

            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
              className="max-w-xl"
            >
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Ride Auto
              </p>

              <h1 className="mt-6 text-5xl font-semibold tracking-tight leading-[0.95] sm:text-6xl lg:text-7xl">
                Автомобили из Азии
                <br />
                как новый стандарт
              </h1>

              <p className="mt-6 text-lg text-muted-foreground leading-relaxed">
                Подбор, проверка и доставка автомобилей без посредников — прозрачный процесс от поиска до передачи.
              </p>

              <div className="mt-10 flex flex-wrap gap-3">
                <Button asChild size="lg" className="h-12 rounded-full px-8">
                  <Link href="/catalog">Смотреть каталог</Link>
                </Button>

                <Button asChild size="lg" variant="secondary" className="h-12 rounded-full px-8">
                  <Link href="/contacts">Обсудить подбор</Link>
                </Button>
              </div>

              <div className="mt-10 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
                {TRUST.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
            </motion.div>

            {/* PARALLAX IMAGE */}
            <motion.div
              style={{ y: heroY, scale: heroScale, opacity: heroOpacity }}
              className="relative flex justify-center"
            >
              <div className="absolute inset-0 scale-110 bg-primary/10 blur-[160px]" />

              <Image
                src={HERO_IMAGE}
                alt="Hero car"
                width={1400}
                height={900}
                priority
                className="relative z-10 object-contain drop-shadow-[0_80px_180px_rgba(0,0,0,0.4)]"
              />
            </motion.div>

          </div>
        </section>

        {/* ================= SCENE 2 ================= */}
        <section className="flex min-h-screen items-center justify-center snap-start px-6">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            className="mx-auto max-w-4xl text-center"
          >
            <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
              Контроль качества
            </p>

            <h2 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl">
              Вы принимаете решение
              <br />
              только после проверки
            </h2>

            <p className="mt-8 text-lg text-muted-foreground">
              Фото, видео и техническая диагностика автомобиля до покупки.
            </p>

            <Link href="/reports" className="mt-10 inline-flex items-center gap-2 text-primary hover:underline">
              Примеры отчётов <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        </section>

        {/* ================= SCENE 3 IMAGE ================= */}
        <section className="flex min-h-screen items-center snap-start px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1 }}
            className="mx-auto w-full max-w-6xl"
          >
            <div className="relative overflow-hidden rounded-[40px] border border-border/60 bg-muted">
              <Image
                src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
                alt="Inspection"
                width={1800}
                height={1000}
                className="object-cover"
              />
            </div>
          </motion.div>
        </section>

        {/* ================= SCENE 4 PROCESS ================= */}
        <section className="flex min-h-screen items-center snap-start px-6">
          <div className="mx-auto w-full max-w-6xl">
            <h2 className="text-4xl font-semibold tracking-tight lg:text-5xl">
              Как проходит покупка
            </h2>

            <div className="mt-24 grid gap-20 lg:grid-cols-4">
              {[
                ["01", "Подбор", "Ищем автомобиль под запрос"],
                ["02", "Проверка", "Видео и технический осмотр"],
                ["03", "Выкуп", "Сделка и экспорт"],
                ["04", "Доставка", "Передача клиенту"],
              ].map(([n, t, d]) => (
                <div key={n}>
                  <div className="text-6xl font-semibold text-muted-foreground/20">{n}</div>
                  <h3 className="mt-6 text-xl font-medium">{t}</h3>
                  <p className="mt-3 text-muted-foreground">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ================= SCENE 5 CTA ================= */}
        <section className="flex min-h-screen items-center snap-start bg-primary px-6 text-primary-foreground">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mx-auto max-w-3xl text-center"
          >
            <h2 className="text-4xl font-semibold sm:text-5xl lg:text-6xl">
              Найдём автомобиль
              <br />
              который вам подходит
            </h2>

            <div className="mt-12 flex flex-wrap justify-center gap-3">
              <Button asChild size="lg" className="h-12 rounded-full px-8">
                <Link href="/catalog">Подобрать авто</Link>
              </Button>

              <Button asChild size="lg" variant="secondary" className="h-12 rounded-full px-8">
                <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                  Telegram
                </a>
              </Button>
            </div>
          </motion.div>
        </section>

      </div>
    </div>
  );
}