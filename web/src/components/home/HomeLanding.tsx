"use client";

import { useState, type ReactNode } from "react";
import {
  motion,
  useReducedMotion,
  useTransform,
  useScroll,
} from "framer-motion";
import { Button } from "@/components/ui/button";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";
import Image from "next/image";
import Link from "next/link";

const LOGO = "WORLD RIDE AUTO";
const TELEGRAM_CHANNEL = "https://t.me/worldrideauto";

const HIGHLIGHTS = [
  {
    title: "Корея, Япония, Китай",
    body: "Подбор с аукционов и площадок под ваш бюджет и класс автомобиля.",
  },
  {
    title: "Проверка до выкупа",
    body: "Фото, видео, диагностика и история — решение принимается на фактах.",
  },
  {
    title: "Сделка под ключ",
    body: "Выкуп, логистика, таможня и документы в одной прозрачной смете.",
  },
  {
    title: "Один менеджер",
    body: "Сопровождение от заявки до передачи автомобиля без переключений между отделами.",
  },
] as const;

const PROCESS_STEPS = [
  ["01", "Профиль", "Фиксируем бюджет, класс автомобиля и сценарий владения."],
  ["02", "Отбор", "Сравниваем площадки Кореи, Японии и Китая, отсеивая слабые варианты."],
  ["03", "Осмотр", "Фото, видео, подключаемая диагностика и проверка истории до покупки."],
  ["04", "Сделка", "Выкуп, логистика, таможня, документы и передача автомобиля."],
] as const;

function LandingButton({
  children,
  className = "",
  href,
  external,
}: {
  children: ReactNode;
  className?: string;
  href: string;
  external?: boolean;
}) {
  return (
    <motion.div
      className="inline-flex"
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.99 }}
      transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
    >
      <Button asChild className={`h-12 rounded-full px-7 text-sm font-semibold ${className}`}>
        {external ? (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ) : (
          <Link href={href}>{children}</Link>
        )}
      </Button>
    </motion.div>
  );
}

/** Абстрактная анимация без рамок и подписей — в общем фоне hero. */
function HeroAmbientMotion() {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) {
    return (
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        initial={false}
      >
        <motion.div className="absolute left-[8%] top-[18%] h-56 w-56 rounded-full bg-foreground/[0.06] blur-3xl" />
        <motion.div className="absolute bottom-[12%] right-[6%] h-72 w-72 rounded-full bg-muted-foreground/10 blur-3xl" />
      </motion.div>
    );
  }

  return (
    <motion.div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <motion.div
        className="absolute -left-[10%] top-[10%] h-[min(52vw,420px)] w-[min(52vw,420px)] rounded-full bg-foreground/[0.05] blur-3xl dark:bg-white/[0.06]"
        animate={{ x: [0, 28, -12, 0], y: [0, -18, 10, 0], scale: [1, 1.06, 0.98, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[8%] right-[-4%] h-[min(58vw,480px)] w-[min(58vw,480px)] rounded-full bg-muted-foreground/12 blur-3xl"
        animate={{ x: [0, -24, 16, 0], y: [0, 14, -8, 0], scale: [1, 0.96, 1.04, 1] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute left-[38%] top-[42%] h-px w-[min(70%,520px)] origin-left bg-gradient-to-r from-transparent via-foreground/20 to-transparent"
        animate={{ opacity: [0.25, 0.55, 0.3], scaleX: [0.85, 1, 0.9] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute left-[22%] top-[28%] h-[min(42vh,320px)] w-px bg-gradient-to-b from-transparent via-foreground/15 to-transparent"
        animate={{ opacity: [0.2, 0.45, 0.25], y: [0, 24, 0] }}
        transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }}
      />
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="absolute h-1.5 w-1.5 rounded-full bg-foreground/25 dark:bg-white/30"
          style={{ left: `${28 + i * 18}%`, top: `${36 + i * 12}%` }}
          animate={{ opacity: [0.15, 0.65, 0.2], scale: [0.8, 1.2, 0.9] }}
          transition={{ duration: 4 + i, repeat: Infinity, ease: "easeInOut", delay: i * 0.6 }}
        />
      ))}
    </motion.div>
  );
}

function HeroVisual() {
  const reduceMotion = useReducedMotion();
  const [videoReady, setVideoReady] = useState(false);
  const showVideo = !reduceMotion;
  const { poster, webm, mp4 } = HOME_LANDING_MEDIA.hero;

  return (
    <div className="relative min-h-[320px] w-full sm:min-h-[400px] lg:min-h-[min(68vh,640px)]">
      <div className="relative mx-auto flex h-full w-full max-w-[640px] items-center justify-center lg:max-w-none">
        <div className="relative aspect-[4/3] w-full max-w-[560px] sm:aspect-[16/11] lg:max-w-none lg:aspect-auto lg:h-[min(68vh,640px)] lg:w-full">
          <div className="absolute inset-0 rounded-[1.75rem] bg-muted/30 dark:bg-muted/20" />
          <Image
            src={poster}
            alt=""
            width={1200}
            height={800}
            priority
            aria-hidden
            className={`relative z-[1] mx-auto h-full w-full object-contain object-center transition-opacity duration-700 ${
              showVideo && videoReady ? "opacity-0" : "opacity-90"
            }`}
          />
          {showVideo && (
            <video
              autoPlay
              muted
              loop
              playsInline
              preload="metadata"
              poster={poster}
              className={`absolute inset-0 z-[1] h-full w-full object-contain transition-opacity duration-700 ${
                videoReady ? "opacity-90" : "opacity-0"
              }`}
              onCanPlay={() => setVideoReady(true)}
            >
              <source src={webm} type="video/webm" />
              <source src={mp4} type="video/mp4" />
            </video>
          )}
          <motion.div
            aria-hidden
            className="absolute inset-0 z-[2] rounded-[1.75rem] bg-gradient-to-t from-background/80 via-transparent to-transparent"
            initial={false}
          />
        </div>
      </div>
    </div>
  );
}

export function HomeLanding() {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const heroScale = useTransform(scrollYProgress, [0, 0.2], reduceMotion ? [1, 1] : [1.02, 1]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.18], [1, 0.92]);

  return (
    <div className="relative isolate overflow-x-hidden bg-background text-foreground">
      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-px w-full origin-left bg-foreground/25"
        aria-hidden
      />

      <section className="relative flex min-h-[calc(100vh-4rem)] items-center overflow-hidden py-12 sm:py-16 lg:min-h-screen lg:py-20">
        <div
          aria-hidden
          className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_70%_0%,var(--muted)_0%,transparent_55%),linear-gradient(180deg,var(--background),var(--background))]"
        />
        <HeroAmbientMotion />

        <div className="relative z-10 mx-auto grid w-full max-w-[1440px] items-center gap-10 px-4 sm:px-6 lg:grid-cols-[0.92fr_1.08fr] lg:gap-14 lg:px-10">
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="inline-flex items-center gap-3 rounded-full border border-border bg-muted/40 px-4 py-2 text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
              <span className="h-px w-8 bg-foreground/20" />
              {LOGO}
            </div>

            <h1 className="mt-7 max-w-4xl text-5xl font-semibold leading-[0.93] tracking-[-0.065em] text-foreground sm:text-6xl lg:text-8xl">
              Автомобили из Азии как предмет точного выбора
            </h1>

            <p className="mt-7 max-w-xl text-lg leading-8 text-muted-foreground">
              Подбор, проверка, выкуп и доставка под ключ. Понятные этапы и прозрачная смета до первого
              платежа.
            </p>

            <motion.div className="mt-10 flex flex-wrap gap-3">
              <LandingButton href="/catalog" className="bg-foreground text-background hover:bg-foreground/90">
                Каталог
              </LandingButton>
              <LandingButton
                href={TELEGRAM_CHANNEL}
                external
                className="border border-border bg-background text-foreground hover:bg-muted"
              >
                Telegram-канал
              </LandingButton>
            </motion.div>
          </motion.div>

          <motion.div
            style={{ scale: heroScale, opacity: heroOpacity }}
            className="order-first lg:order-none"
          >
            <HeroVisual />
          </motion.div>
        </div>
      </section>

      <section className="border-y border-border bg-muted/25 py-14 sm:py-16" aria-label="О сервисе">
        <motion.div
          id="company"
          className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10"
          initial={reduceMotion ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
        >
          <p className="max-w-2xl text-sm uppercase tracking-[0.22em] text-muted-foreground">О компании</p>
          <p className="mt-4 max-w-3xl text-lg leading-8 text-foreground sm:text-xl">
            World Ride Auto — импорт автомобилей из Кореи, Японии и Китая с проверкой до выкупа и
            сопровождением сделки до вручения.
          </p>
        </motion.div>
        <div className="mx-auto mt-10 grid max-w-[1440px] gap-3 px-4 sm:mt-12 sm:grid-cols-2 sm:px-6 lg:grid-cols-4 lg:px-10">
          {HIGHLIGHTS.map((item, i) => (
            <motion.div
              key={item.title}
              initial={reduceMotion ? false : { opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06 }}
              className="rounded-2xl border border-border bg-card p-5 shadow-sm"
            >
              <h3 className="text-base font-semibold text-foreground">{item.title}</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.body}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="py-16 sm:py-24" aria-label="Процесс">
        <motion.div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
          <motion.h2
            className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-foreground sm:text-5xl lg:text-6xl"
            initial={reduceMotion ? false : { opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            Полный цикл без лишних декораций
          </motion.h2>
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PROCESS_STEPS.map(([n, t, d], i) => (
              <motion.div
                key={n}
                initial={reduceMotion ? false : { opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="min-h-[220px] rounded-2xl border border-border bg-card p-5 shadow-sm"
              >
                <motion.div className="text-5xl font-semibold tracking-[-0.06em] text-muted-foreground/30" aria-hidden>
                  {n}
                </motion.div>
                <div className="mt-10 text-xl font-semibold text-foreground">{t}</div>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{d}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </section>

      <section className="border-t border-border bg-muted/30 py-20 sm:py-28">
        <motion.div
          className="mx-auto max-w-3xl px-4 text-center sm:px-6"
          initial={reduceMotion ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl lg:text-5xl">
            Подберём автомобиль под ваш запрос
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-muted-foreground sm:text-lg">
            Оставьте заявку в каталоге или напишите в Telegram — обсудим бюджет, сроки и варианты из Азии.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <LandingButton href="/catalog" className="bg-foreground text-background hover:bg-foreground/90">
              Подобрать авто
            </LandingButton>
            <LandingButton
              href={TELEGRAM_CHANNEL}
              external
              className="border border-border bg-background text-foreground hover:bg-muted"
            >
              Telegram-канал
            </LandingButton>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
