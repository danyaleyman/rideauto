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
import { useRef, useEffect } from "react";
import { ChevronDown } from "lucide-react";

const HERO_IMAGE = "/assets/landing-main-page.png";

const TRUST = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"];

export function HomeLanding() {
  const containerRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef(null);

  const { scrollYProgress, scrollY } = useScroll({
    container: containerRef
  });

  // smooth physics scroll
  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 25,
  });

  // cinematic camera system
  const heroScale = useTransform(scrollY, [0, 800], [1.2, 1]);
  const heroY = useTransform(scrollY, [0, 800], [0, 100]);
  const heroOpacity = useTransform(scrollY, [0, 500], [1, 0.8]);

  const nextScale = useTransform(scrollY, [300, 900], [0.95, 1]);

  // scroll to next section
  const scrollToNext = () => {
    if (containerRef.current) {
      const sections = containerRef.current.children;
      const currentScroll = containerRef.current.scrollTop;
      const windowHeight = window.innerHeight;
      const nextScroll = Math.ceil(currentScroll / windowHeight) * windowHeight;
      containerRef.current.scrollTo({ top: nextScroll + windowHeight, behavior: "smooth" });
    }
  };

  // hide scrollbar
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "auto";
    };
  }, []);

  // bounce animation for arrow
  const bounceAnimation = {
    y: [0, -8, 0, -4, 0],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut" as const
    }
  };

  return (
    <div className="relative bg-background">
      {/* hide scrollbar */}
      <style jsx global>{`
        body {
          overflow: hidden !important;
        }
        ::-webkit-scrollbar {
          display: none !important;
        }
        * {
          scrollbar-width: none !important;
        }
      `}</style>

      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: smoothProgress }}
        className="fixed top-0 left-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* Scroll down indicator */}
      <motion.div
        animate={bounceAnimation}
        className="fixed bottom-8 left-1/2 z-40 hidden -translate-x-1/2 cursor-pointer rounded-full bg-background/80 p-2 backdrop-blur sm:block"
        onClick={scrollToNext}
      >
        <ChevronDown className="h-5 w-5 text-foreground" />
      </motion.div>

      <div 
        ref={containerRef}
        className="relative h-screen snap-y snap-mandatory overflow-y-scroll"
        style={{ scrollBehavior: "smooth" }}
      >

        {/* ================= HERO ================= */}
        <section className="relative min-h-screen flex items-center snap-start overflow-hidden">

          {/* cinematic background layers */}
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -top-40 right-[-20%] h-[700px] w-[700px] rounded-full bg-primary/20 blur-[180px]" />
            <div className="absolute bottom-[-30%] left-[-20%] h-[700px] w-[700px] rounded-full bg-blue-500/10 blur-[200px]" />
          </div>

          <div className="mx-auto grid w-full max-w-7xl grid-cols-1 lg:grid-cols-2 items-center px-5 sm:px-6 gap-8 lg:gap-12">

            {/* TEXT */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7 }}
              className="relative z-20 max-w-xl"
            >
              <p className="text-xs tracking-[0.35em] uppercase text-muted-foreground">
                Ride Auto
              </p>

              <h1 className="mt-4 text-4xl sm:text-5xl lg:text-6xl xl:text-7xl font-semibold leading-[1.05]">
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
                  <Link href="/catalog">Смотреть каталог</Link>
                </Button>

                <Button asChild size="lg" variant="secondary" className="rounded-full px-8">
                  <Link href="/contacts">Обсудить</Link>
                </Button>
              </div>

              <div className="mt-8 flex flex-wrap gap-4 text-sm text-muted-foreground">
                {TRUST.map((t) => (
                  <span key={t}>{t}</span>
                ))}
              </div>
            </motion.div>

            {/* IMAGE */}
            <motion.div
              ref={heroRef}
              style={{ scale: heroScale, y: heroY, opacity: heroOpacity }}
              className="relative flex justify-center lg:justify-end"
            >
              <div className="absolute inset-0 scale-125 bg-primary/10 blur-[160px]" />

              <Image
                src={HERO_IMAGE}
                alt="Hero car"
                width={2400}
                height={1600}
                priority
                className="
                  w-full
                  max-w-[1100px] lg:max-w-[1350px]
                  object-contain
                  drop-shadow-[0_100px_220px_rgba(0,0,0,0.35)]
                "
              />
            </motion.div>

          </div>
        </section>

        {/* ================= TECH EDGE (НОВЫЙ БЛОК ПРО ЭКСПЕРТИЗУ) ================= */}
        <section className="min-h-[50vh] flex items-center snap-start px-5 sm:px-6">
          <div className="mx-auto max-w-6xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-muted/30 px-3 py-1 text-xs">
              <span className="text-primary">●</span> Своя аналитика
            </div>
            <h3 className="mt-4 text-2xl font-medium tracking-tight sm:text-3xl">
              Прямой доступ к <span className="text-primary">аукционам и площадкам</span> Кореи и Китая
            </h3>
            <p className="mt-3 max-w-2xl mx-auto text-muted-foreground">
              Без посредников и наценок. Показываем скрины с систем, фиксируем ставку.
            </p>
          </div>
        </section>

        {/* ================= SCENE 2 ================= */}
        <section className="min-h-screen flex items-center justify-center snap-start px-5 sm:px-6">
          <motion.div
            style={{ scale: nextScale }}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            className="mx-auto max-w-4xl text-center"
          >
            <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
              Контроль качества
            </p>

            <h2 className="mt-5 text-3xl sm:text-4xl lg:text-5xl font-semibold leading-tight">
              Вы принимаете решение
              <br />
              только после проверки
            </h2>

            <p className="mt-5 text-muted-foreground sm:text-lg">
              Фото, видео и техническая диагностика автомобиля до покупки.
            </p>

            <Link
              href="/reports"
              className="mt-6 inline-flex items-center gap-1 text-primary hover:underline"
            >
              Примеры отчётов
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </motion.div>
        </section>

        {/* ================= SCENE 3 ================= */}
        <section className="min-h-screen flex items-center snap-start px-5 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <div className="overflow-hidden rounded-3xl border shadow-xl bg-muted">
              <Image
                src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
                alt="Осмотр автомобиля"
                width={1800}
                height={1000}
                className="object-cover transition-transform duration-700 hover:scale-[1.02]"
              />
            </div>
          </div>
        </section>

        {/* ================= SCENE 4 ================= */}
        <section className="min-h-screen flex items-center snap-start px-5 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-semibold">
              Как проходит покупка
            </h2>

            <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["01", "Подбор", "Ищем авто под запрос"],
                ["02", "Проверка", "Видео и диагностика"],
                ["03", "Выкуп", "Сделка и документы"],
                ["04", "Доставка", "Передача клиенту"],
              ].map(([n, t, d], idx) => (
                <motion.div
                  key={n}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <div className="text-6xl font-semibold text-muted-foreground/20">{n}</div>
                  <h3 className="mt-3 text-xl font-medium">{t}</h3>
                  <p className="mt-2 text-muted-foreground">{d}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        {/* ================= CTA ================= */}
        <section className="relative min-h-screen flex items-center snap-start px-5 sm:px-6">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/90 to-primary/70" />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.15),transparent_60%)]" />

          <div className="relative mx-auto max-w-3xl text-center text-white">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-semibold leading-tight">
              Найдём автомобиль,
              <br />
              который вам подходит
            </h2>

            <div className="mt-10 flex flex-wrap justify-center gap-3">
              <Button asChild size="lg" className="rounded-full bg-white text-black hover:bg-white/90 px-8">
                <Link href="/catalog">Подобрать авто</Link>
              </Button>

              <Button asChild size="lg" className="rounded-full border border-white/30 bg-white/10 text-white backdrop-blur hover:bg-white/20 px-8">
                <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                  Telegram
                </a>
              </Button>
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}