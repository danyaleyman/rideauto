"use client";

import { useEffect, useState, type ReactNode } from "react";
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

const HERO_MEDIA_CLASS =
  "pointer-events-none mx-auto h-full w-full max-h-[min(52vh,420px)] object-contain object-center sm:max-h-[min(58vh,480px)] lg:max-h-[min(68vh,640px)]";

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

function useHeroVideoEnabled() {
  const reduceMotion = useReducedMotion();
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setEnabled(mq.matches && !reduceMotion);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [reduceMotion]);

  return enabled;
}

function HeroVisual() {
  const videoEnabled = useHeroVideoEnabled();
  const [videoReady, setVideoReady] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const { fallback, webm } = HOME_LANDING_MEDIA.hero;
  const showVideo = videoEnabled && !videoFailed;
  const showFallbackImage = !showVideo || !videoReady;

  return (
    <motion.div className="relative w-full bg-transparent shadow-none">
      <motion.div
        className="relative mx-auto flex aspect-[4/3] w-full max-w-[min(100%,720px)] items-center justify-center bg-transparent sm:aspect-[16/10] lg:aspect-[16/9] lg:max-w-none"
        aria-hidden
      >
        <Image
          src={fallback}
          alt=""
          width={1400}
          height={900}
          priority
          unoptimized
          className={`${HERO_MEDIA_CLASS} transition-opacity duration-500 ${
            showFallbackImage ? "relative z-[1] opacity-100" : "absolute inset-0 z-[1] opacity-0"
          }`}
        />
        {showVideo && (
          <video
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            className={`absolute inset-0 z-[2] ${HERO_MEDIA_CLASS} transition-opacity duration-500 ${
              videoReady ? "opacity-100" : "opacity-0"
            }`}
            onCanPlay={() => setVideoReady(true)}
            onError={() => setVideoFailed(true)}
          >
            <source src={webm} type="video/webm" />
          </video>
        )}
      </motion.div>
    </motion.div>
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

      <section className="relative flex min-h-[calc(100vh-4rem)] items-center overflow-hidden bg-background py-12 sm:py-16 lg:min-h-screen lg:py-20">
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
            className="order-first bg-transparent shadow-none lg:order-none"
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
                <div className="text-5xl font-semibold tracking-[-0.06em] text-muted-foreground/30" aria-hidden>
                  {n}
                </div>
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
