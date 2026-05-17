"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  motion,
  useMotionValueEvent,
  useReducedMotion,
  useSpring,
  useTransform,
  useInView,
  useScroll,
} from "framer-motion";
import { Button } from "@/components/ui/button";
import { HOME_LANDING_MEDIA } from "@/lib/home-landing-media";
import Image from "next/image";
import Link from "next/link";

const SURFACE =
  "border-stone-900/10 bg-stone-900/[0.03] dark:border-white/[0.08] dark:bg-white/[0.03]";
const MUTED = "text-stone-600/80 dark:text-stone-300/72";
const HEADING = "text-stone-900 dark:text-stone-50";
const ACCENT = "text-[#9a8458] dark:text-[#d6c6a0]";

const LOGO = "WORLD RIDE AUTO";
const TELEGRAM_CHANNEL = "https://t.me/worldrideauto";

const TRUST_BRANDS = ["Korea", "Japan", "China", "Auction", "Diagnostics", "Logistics", "Customs", "Handover"];
const STATS = [
  { label: "направления", value: 3 },
  { label: "точек контроля", value: 12, suffix: "+" },
  { label: "этапа сделки", value: 4 },
  { label: "сопровождение", value: 1, suffix: " менеджер" },
];

const PROCESS_STEPS = [
  ["01", "Профиль", "Фиксируем бюджет, класс автомобиля и сценарий владения."],
  ["02", "Отбор", "Сравниваем площадки Кореи, Японии и Китая, отсеивая слабые варианты."],
  ["03", "Осмотр", "Фото, видео, подключаемая диагностика и проверка истории до покупки."],
  ["04", "Сделка", "Выкуп, логистика, таможня, документы и передача автомобиля."],
] as const;

function NoiseOverlay() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[20] opacity-[0.045]"
      style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
      }}
    />
  );
}

function CinemaButton({
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
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.985 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
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

function AnimatedNumber({
  value,
  suffix = "",
}: {
  value: number;
  suffix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const springValue = useSpring(0, { bounce: 0, duration: 1.5 });
  const [display, setDisplay] = useState(`0${suffix}`);

  useEffect(() => {
    if (inView) springValue.set(value);
  }, [inView, value, springValue]);

  useMotionValueEvent(springValue, "change", (latest) => {
    setDisplay(`${Math.round(latest).toLocaleString("ru-RU")}${suffix}`);
  });

  return <span ref={ref}>{display}</span>;
}

function Marquee({ items, paused }: { items: string[]; paused?: boolean }) {
  return (
    <motion.div
      aria-hidden
      className={`overflow-hidden border-y py-3 backdrop-blur-sm ${SURFACE}`}
    >
      <motion.div
        className="flex gap-12 whitespace-nowrap text-xs uppercase tracking-[0.26em] text-stone-500/55 dark:text-stone-300/45"
        animate={paused ? undefined : { x: ["0%", "-50%"] }}
        transition={paused ? undefined : { repeat: Infinity, duration: 38, ease: "linear" }}
      >
        {[...items, ...items].map((item, i) => (
          <span key={`${item}-${i}`} className="flex items-center gap-2">
            <span className="h-px w-6 bg-stone-900/15 dark:bg-stone-200/25" />
            {item}
          </span>
        ))}
      </motion.div>
    </motion.div>
  );
}

function HeroMedia() {
  const reduceMotion = useReducedMotion();
  const [videoReady, setVideoReady] = useState(false);
  const showVideo = !reduceMotion;
  const { poster, webm, mp4 } = HOME_LANDING_MEDIA.hero;

  return (
    <motion.div
      className={`relative h-full min-h-[360px] w-full overflow-hidden rounded-[2rem] border shadow-[0_40px_120px_rgba(15,15,15,0.14)] dark:shadow-[0_60px_180px_rgba(0,0,0,0.45)] sm:min-h-[460px] lg:min-h-[68vh] ${SURFACE} bg-[radial-gradient(circle_at_50%_20%,rgba(214,198,160,0.22),rgba(214,198,160,0)_34%),linear-gradient(145deg,rgba(255,255,255,0.85),rgba(246,242,234,0.92))] dark:bg-[radial-gradient(circle_at_50%_20%,rgba(255,255,255,0.12),rgba(255,255,255,0)_34%),linear-gradient(145deg,rgba(255,255,255,0.07),rgba(255,255,255,0.015))]`}
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="absolute inset-x-6 top-6 z-10 flex items-center justify-between text-[10px] uppercase tracking-[0.28em] text-stone-300/50">
        <span>Hero media slot</span>
        <span>3D / animation ready</span>
      </div>
      <Image
        src={poster}
        alt=""
        width={1200}
        height={800}
        priority
        aria-hidden
        className={`absolute inset-0 mx-auto h-full w-[120%] max-w-none object-contain drop-shadow-[0_110px_180px_rgba(0,0,0,0.42)] transition-opacity duration-700 sm:w-[130%] lg:w-[145%] ${
          showVideo && videoReady ? "opacity-0" : "opacity-100"
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
          className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-700 ${
            videoReady ? "opacity-100" : "opacity-0"
          }`}
          onCanPlay={() => setVideoReady(true)}
        >
          <source src={webm} type="video/webm" />
          <source src={mp4} type="video/mp4" />
        </video>
      )}
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(7,7,7,0.05),rgba(7,7,7,0.36)_72%,rgba(7,7,7,0.68))]" />
      <div className="absolute bottom-6 left-6 right-6 z-10 flex flex-wrap items-end justify-between gap-4 border-t border-white/[0.08] pt-5">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-stone-300/55">Next drop</p>
          <p className="mt-1 max-w-sm text-sm text-stone-100/75">
            Сюда встанет ваша финальная анимация и 3D-модель без изменения структуры hero.
          </p>
        </div>
        <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-stone-200/70">
          16:9 / alpha / loop
        </span>
      </div>
    </motion.div>
  );
}

function SceneMediaCard({
  eyebrow,
  title,
  description,
  items,
  mediaSrc,
  mediaAlt,
  align = "right",
}: {
  eyebrow: string;
  title: string;
  description: string;
  items: string[];
  mediaSrc?: string;
  mediaAlt?: string;
  align?: "left" | "right";
}) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.article
      initial={reduceMotion ? false : { opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-120px" }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className={`grid gap-8 rounded-[2rem] border border-white/[0.08] bg-white/[0.035] p-4 shadow-[0_40px_130px_rgba(0,0,0,0.32)] backdrop-blur-sm lg:grid-cols-[1fr_0.9fr] lg:p-6 ${
        align === "left" ? "lg:grid-cols-[0.9fr_1fr]" : ""
      }`}
    >
      <div
        className={`relative min-h-[280px] overflow-hidden rounded-[1.5rem] border border-white/[0.08] bg-[radial-gradient(circle_at_70%_20%,rgba(214,198,160,0.16),rgba(214,198,160,0)_34%),linear-gradient(135deg,rgba(255,255,255,0.08),rgba(255,255,255,0.015))] ${
          align === "left" ? "lg:order-2" : ""
        }`}
      >
        <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.08),rgba(255,255,255,0)_38%),radial-gradient(circle_at_20%_80%,rgba(255,255,255,0.1),rgba(255,255,255,0)_28%)]" />
        <div className="absolute left-5 top-5 rounded-full border border-white/10 bg-black/25 px-3 py-1 text-[10px] uppercase tracking-[0.28em] text-stone-200/60">
          Media slot
        </div>
        <div className="absolute inset-x-5 bottom-5 rounded-2xl border border-white/[0.08] bg-black/30 p-4 backdrop-blur-md">
          <p className="text-xs uppercase tracking-[0.24em] text-stone-300/50">Replace with render</p>
          <p className="mt-2 text-sm text-stone-100/75">
            Положите сюда рендер/видео осмотра, диагностики или логистики, когда материалы будут готовы.
          </p>
        </div>
      </div>

      <div className="flex flex-col justify-center px-2 py-4 lg:px-6">
        <p className="text-xs uppercase tracking-[0.34em] text-[#d6c6a0]/75">{eyebrow}</p>
        <h2 className="mt-4 max-w-xl text-3xl font-semibold tracking-[-0.04em] text-stone-50 sm:text-4xl lg:text-5xl">
          {title}
        </h2>
        <p className="mt-5 max-w-xl text-base leading-7 text-stone-300/72 sm:text-lg">{description}</p>
        <div className="mt-8 grid gap-3">
          {items.map((item) => (
            <div key={item} className="flex items-center gap-3 text-sm text-stone-200/76">
              <span className="h-px w-8 bg-[#d6c6a0]/45" />
              {item}
            </div>
          ))}
        </div>
      </div>
    </motion.article>
  );
}

export function HomeLanding() {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const heroScale = useTransform(scrollYProgress, [0, 0.2], reduceMotion ? [1, 1] : [1.03, 1]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.18], [1, 0.88]);

  return (
    <motion.div className="relative isolate overflow-x-hidden bg-[#f6f2ea] text-stone-900 selection:bg-[#d6c6a0]/30 dark:bg-[#080806] dark:text-stone-50 dark:selection:bg-[#d6c6a0]/25">
      <NoiseOverlay />

      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed left-0 top-0 z-50 h-px w-full origin-left bg-[#d6c6a0]/70"
        aria-hidden
      />

      <section className="relative flex min-h-[calc(100vh-4rem)] items-center overflow-hidden py-12 sm:py-16 lg:min-h-screen lg:py-20">
        <div
          aria-hidden
          className="absolute inset-0 bg-[radial-gradient(circle_at_72%_18%,rgba(214,198,160,0.22),rgba(214,198,160,0)_30%),radial-gradient(circle_at_12%_18%,rgba(255,255,255,0.65),rgba(255,255,255,0)_26%),linear-gradient(180deg,#faf7f0,#f6f2ea_52%,#efe9dd)] dark:bg-[radial-gradient(circle_at_72%_18%,rgba(214,198,160,0.16),rgba(214,198,160,0)_30%),radial-gradient(circle_at_12%_18%,rgba(255,255,255,0.08),rgba(255,255,255,0)_26%),linear-gradient(180deg,#11100d,#080806_52%,#050504)]"
        />
        <div
          aria-hidden
          className="absolute inset-x-0 bottom-0 h-48 bg-gradient-to-t from-[#f6f2ea] to-transparent dark:from-[#080806]"
        />

        <motion.div className="relative z-10 mx-auto w-full max-w-[1440px] px-4 sm:px-6 lg:px-10">
          <motion.div className="grid items-center gap-10 lg:grid-cols-[0.88fr_1.12fr] lg:gap-14">
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className={`inline-flex items-center gap-3 rounded-full border px-4 py-2 text-[11px] uppercase tracking-[0.28em] ${SURFACE} ${ACCENT}`}>
                <span className="h-px w-8 bg-[#9a8458]/55 dark:bg-[#d6c6a0]/55" />
                {LOGO}
              </div>

              <h1 className={`mt-7 max-w-4xl text-5xl font-semibold leading-[0.93] tracking-[-0.065em] sm:text-6xl lg:text-8xl ${HEADING}`}>
                Автомобили из Азии как предмет точного выбора
              </h1>

              <p className={`mt-7 max-w-xl text-lg leading-8 ${MUTED}`}>
                Подбор, проверка, выкуп и доставка под ключ. Без визуального шума, без скрытых этапов, с понятной
                картиной сделки до первого платежа.
              </p>

              <div className="mt-10 flex flex-wrap gap-3">
                <CinemaButton
                  href="/catalog"
                  className="bg-stone-50 text-stone-950 shadow-[0_20px_70px_rgba(255,255,255,0.12)] hover:bg-[#d6c6a0]"
                >
                  Каталог
                </CinemaButton>
                <CinemaButton
                  href={TELEGRAM_CHANNEL}
                  external
                  className={`border ${SURFACE} ${HEADING} hover:bg-stone-900/[0.04] dark:hover:bg-white/[0.08]`}
                >
                  Telegram-канал
                </CinemaButton>
              </div>

              <motion.div
                className="mt-10 grid max-w-xl grid-cols-2 gap-2 sm:grid-cols-3"
                initial={reduceMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.35, duration: 0.6 }}
              >
                {["Китай", "Корея", "Япония", "Видеоосмотр", "Диагностика", "Доставка"].map((badge) => (
                  <span
                    key={badge}
                    className={`rounded-2xl border px-3 py-2 text-sm ${SURFACE} ${MUTED}`}
                  >
                    {badge}
                  </span>
                ))}
              </motion.div>
            </motion.div>

            <motion.div style={{ scale: heroScale, opacity: heroOpacity }} className="order-first lg:order-none">
              <HeroMedia />
            </motion.div>
          </motion.div>
        </motion.div>
      </section>

      <Marquee items={TRUST_BRANDS} paused={!!reduceMotion} />

      <section className="relative py-16 sm:py-20" aria-label="Показатели сервиса">
        <div className="mx-auto grid max-w-[1440px] grid-cols-2 gap-3 px-4 sm:px-6 lg:grid-cols-4 lg:px-10">
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className={`rounded-[1.5rem] border p-5 backdrop-blur-sm sm:p-6 ${SURFACE}`}
            >
              <div className={`text-3xl font-semibold tracking-[-0.04em] lg:text-5xl ${HEADING}`}>
                <AnimatedNumber value={stat.value} suffix={stat.suffix} />
              </div>
              <div className={`mt-2 text-sm ${MUTED}`}>{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      <section id="company" className="py-16 sm:py-24">
        <div className="mx-auto grid max-w-[1440px] gap-5 px-4 sm:px-6 lg:px-10">
          <SceneMediaCard
            eyebrow="Inspection"
            title="Осмотр до покупки, а не после сюрпризов"
            description="Материалы осмотра становятся частью решения: кузов, салон, документы, диагностический сканер и видеофиксация состояния."
            items={["Фото и видео по чек-листу", "Подключаемая диагностика", "Проверка истории и документов"]}
          />
          <SceneMediaCard
            eyebrow="Source"
            title="Источник автомобиля виден до сделки"
            description="Показываем, откуда берётся конкретный автомобиль, почему он проходит отбор и какие риски уже закрыты до выкупа."
            items={["Аукционы и площадки Азии", "Сравнение альтернатив", "Понятная смета до оплаты"]}
            align="left"
          />
        </div>
      </section>

      <section className="py-16 sm:py-24" aria-label="Процесс">
        <div className="mx-auto max-w-[1440px] px-4 sm:px-6 lg:px-10">
          <motion.h2
            className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-stone-50 sm:text-5xl lg:text-6xl"
            initial={reduceMotion ? false : { opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            Полный цикл без лишних декораций
          </motion.h2>
          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {PROCESS_STEPS.map(([n, t, d], i) => (
              <motion.div
                key={n}
                initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="min-h-[220px] rounded-[1.5rem] border border-white/[0.08] bg-white/[0.03] p-5"
              >
                <div className="text-5xl font-semibold tracking-[-0.06em] text-white/12">{n}</div>
                <div className="mt-10 text-xl font-semibold text-stone-50">{t}</div>
                <p className="mt-3 text-sm leading-6 text-stone-300/62">{d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden py-24 sm:py-32">
        <div aria-hidden className="absolute inset-0 bg-[radial-gradient(circle_at_50%_15%,rgba(214,198,160,0.13),rgba(214,198,160,0)_34%),linear-gradient(180deg,#080806,#030302)]" />
        <motion.div
          className="relative mx-auto max-w-4xl px-4 text-center sm:px-6"
          initial={reduceMotion ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <p className="text-xs uppercase tracking-[0.34em] text-[#d6c6a0]/70">Ready for media</p>
          <h2 className="mt-5 text-4xl font-semibold leading-[0.98] tracking-[-0.06em] text-stone-50 sm:text-5xl lg:text-7xl">
            Когда медиа будет готово, лендинг уже выдержит уровень
          </h2>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-stone-300/68">
            Hero, сцены осмотра и карточки процесса подготовлены так, чтобы заменить плейсхолдеры на ваши рендеры,
            видео и 3D без перестройки страницы.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <CinemaButton
              href="/catalog"
              className="bg-stone-50 text-stone-950 hover:bg-[#d6c6a0]"
            >
              Подобрать авто
            </CinemaButton>
            <CinemaButton
              href={TELEGRAM_CHANNEL}
              external
              className="border border-white/[0.12] bg-white/[0.035] text-stone-100 hover:bg-white/[0.08]"
            >
              Telegram-канал
            </CinemaButton>
          </div>
        </motion.div>
      </section>
    </motion.div>
  );
}
