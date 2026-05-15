"use client";

import { motion, useScroll, useTransform } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, ChevronDown } from "lucide-react";
import { useRef, useEffect } from "react";

const HERO_IMAGE = "/assets/landing-main-page.png";

const TRUST = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"];

export function HomeLanding() {
  const heroRef = useRef(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ container: containerRef });
  const { scrollY } = useScroll({ container: containerRef });
  
  // Прячем scrollbar и настраиваем плавный скролл
  useEffect(() => {
    document.body.style.overflow = "hidden";
    
    // Плавный скролл для якорных ссылок
    const handleAnchorClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const anchor = target.closest('a');
      if (anchor?.hash && anchor.hash.startsWith('#')) {
        e.preventDefault();
        const element = document.querySelector(anchor.hash);
        if (element && containerRef.current) {
          const offset = element.getBoundingClientRect().top + containerRef.current.scrollTop;
          containerRef.current.scrollTo({ top: offset, behavior: 'smooth' });
        }
      }
    };
    
    document.addEventListener('click', handleAnchorClick);
    
    return () => {
      document.body.style.overflow = "auto";
      document.removeEventListener('click', handleAnchorClick);
    };
  }, []);

  const heroY = useTransform(scrollY, [0, 500], [0, 100]);
  const heroScale = useTransform(scrollY, [0, 500], [1, 0.98]);
  const heroOpacity = useTransform(scrollY, [0, 300], [1, 0.8]);

  // Анимация для bounce стрелки
  const bounceAnimation = {
    y: [0, -10, 0, -5, 0],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut" as const
    }
  };

  // Плавный скролл вниз
  const scrollToNext = () => {
    if (containerRef.current) {
      const nextSection = containerRef.current.children[1] as HTMLElement;
      if (nextSection) {
        nextSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }
  };

  return (
    <div className="relative">
      {/* PROGRESS BAR */}
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* Scroll down indicator */}
      <motion.div
        animate={bounceAnimation}
        className="fixed bottom-8 left-1/2 z-40 hidden -translate-x-1/2 cursor-pointer rounded-full bg-background/80 p-2 backdrop-blur sm:block"
        onClick={scrollToNext}
      >
        <ChevronDown className="h-6 w-6 text-foreground" />
      </motion.div>

      {/* Hide scrollbar */}
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
        html {
          scroll-behavior: smooth;
        }
      `}</style>

      <div 
        ref={containerRef}
        className="relative h-screen snap-y snap-mandatory overflow-y-scroll scroll-smooth"
        style={{ scrollBehavior: 'smooth' }}
      >

        {/* ================= HERO (SCENE 1) ================= */}
        <section ref={heroRef} className="relative flex min-h-screen items-center snap-start overflow-hidden">

          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -top-40 right-[-10%] h-[600px] w-[600px] rounded-full bg-primary/20 blur-[160px]" />
            <div className="absolute bottom-[-30%] left-[-10%] h-[600px] w-[600px] rounded-full bg-blue-500/10 blur-[180px]" />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-background/50" />
          </div>

          <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-center gap-8 px-6 lg:grid-cols-[1fr_1.1fr] lg:gap-12 xl:gap-16">

            {/* LEFT TEXT */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
              className="max-w-xl"
            >
              <p className="text-xs uppercase tracking-[0.35em] text-muted-foreground">
                Ride Auto
              </p>

              <h1 className="mt-6 text-4xl font-semibold tracking-tight leading-[1.05] sm:text-5xl lg:text-6xl xl:text-7xl">
                Автомобили из Азии
                <br />
                как новый стандарт
              </h1>

              <p className="mt-6 text-base text-muted-foreground leading-relaxed sm:text-lg">
                Подбор, проверка и доставка автомобилей без посредников — прозрачный процесс от поиска до передачи.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Button asChild size="lg" className="h-12 rounded-full px-8">
                  <Link href="/catalog">Смотреть каталог</Link>
                </Button>

                <Button asChild size="lg" variant="secondary" className="h-12 rounded-full px-8">
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

            {/* RIGHT IMAGE - увеличенный размер */}
            <motion.div
              style={{ y: heroY, scale: heroScale, opacity: heroOpacity }}
              className="relative flex justify-center lg:justify-end"
            >
              <div className="absolute inset-0 scale-110 bg-primary/10 blur-[160px]" />

              <Image
                src={HERO_IMAGE}
                alt="Hero car"
                width={1600}
                height={1000}
                priority
                className="relative z-10 w-full max-w-2xl object-contain drop-shadow-[0_80px_180px_rgba(0,0,0,0.3)] lg:max-w-none"
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

            <h2 className="mt-6 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl xl:text-6xl">
              Вы принимаете решение
              <br />
              только после проверки
            </h2>

            <p className="mt-6 text-base text-muted-foreground sm:text-lg">
              Фото, видео и техническая диагностика автомобиля до покупки.
            </p>

            <Link href="/reports" className="group mt-10 inline-flex items-center gap-2 text-primary hover:underline">
              Примеры отчётов 
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </motion.div>
        </section>

        {/* ================= SCENE 3 IMAGE ================= */}
        <section className="flex min-h-screen items-center snap-start px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="mx-auto w-full max-w-6xl"
          >
            <div className="relative overflow-hidden rounded-[40px] border border-border/60 bg-muted shadow-xl">
              <Image
                src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
                alt="Inspection"
                width={1800}
                height={1000}
                className="object-cover transition-transform duration-700 hover:scale-[1.02]"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-background/20 to-transparent" />
            </div>
          </motion.div>
        </section>

        {/* ================= SCENE 4 PROCESS ================= */}
        <section className="flex min-h-screen items-center snap-start px-6">
          <div className="mx-auto w-full max-w-6xl">
            <motion.h2
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl"
            >
              Как проходит покупка
            </motion.h2>

            <div className="mt-16 grid gap-12 sm:mt-24 lg:grid-cols-4 lg:gap-20">
              {[
                ["01", "Подбор", "Ищем автомобиль под запрос и бюджет"],
                ["02", "Проверка", "Видео и технический осмотр"],
                ["03", "Выкуп", "Сделка и экспорт документов"],
                ["04", "Доставка", "Передача автомобиля клиенту"],
              ].map(([n, t, d], idx) => (
                <motion.div
                  key={n}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: idx * 0.1 }}
                >
                  <div className="text-6xl font-semibold text-muted-foreground/20 transition-colors group-hover:text-muted-foreground/40 sm:text-7xl">
                    {n}
                  </div>
                  <h3 className="mt-4 text-xl font-medium sm:text-2xl">{t}</h3>
                  <p className="mt-2 text-sm text-muted-foreground sm:text-base">{d}</p>
                </motion.div>
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
            <h2 className="text-3xl font-semibold sm:text-4xl lg:text-5xl xl:text-6xl">
              Найдём автомобиль,
              <br />
              который вам подходит
            </h2>

            <div className="mt-10 flex flex-wrap justify-center gap-3 sm:mt-12">
              <Button asChild size="lg" className="h-12 rounded-full bg-white text-primary hover:bg-white/90 sm:h-14 sm:px-10">
                <Link href="/catalog">Подобрать авто</Link>
              </Button>

              <Button asChild size="lg" variant="secondary" className="h-12 rounded-full border border-white/20 bg-white/10 text-white backdrop-blur hover:bg-white/20 sm:h-14 sm:px-10">
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