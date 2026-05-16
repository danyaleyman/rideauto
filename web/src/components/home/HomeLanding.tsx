"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  motion,
  useMotionValue,
  useMotionValueEvent,
  useReducedMotion,
  useSpring,
  useTransform,
  useInView,
  useScroll,
} from "framer-motion";
import { Button } from "@/components/ui/button";
import Image from "next/image";
import Link from "next/link";

const LOGO = "WORLD RIDE AUTO";
const TRUST_BRANDS = [
  "USS",
  "TAA",
  "JU",
  "AUCNET",
  "Toyota",
  "Lexus",
  "BMW",
  "Mercedes",
  "Honda",
  "Nissan",
  "Hyundai",
  "Kia",
];
const STATS = [
  { label: "Авто доставлено", value: 1240 },
  { label: "Средний срок", value: 11, suffix: " дней" },
  { label: "Довольных клиентов", value: 980 },
  { label: "Экономия vs рынок", value: 35, suffix: "%" },
];

const PROCESS_STEPS = [
  ["01", "Подбор"],
  ["02", "Проверка"],
  ["03", "Выкуп"],
  ["04", "Доставка"],
] as const;

function useIsTouchDevice() {
  const [isTouch, setIsTouch] = useState(false);
  useEffect(() => {
    setIsTouch(
      typeof window !== "undefined" &&
        ("ontouchstart" in window || navigator.maxTouchPoints > 0),
    );
  }, []);
  return isTouch;
}

function NoiseOverlay() {
  return (
    <motion.div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[60] opacity-[0.035]"
      style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
      }}
    />
  );
}

function CustomCursor() {
  const reduceMotion = useReducedMotion();
  const isTouch = useIsTouchDevice();
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);
  const springConfig = { damping: 25, stiffness: 700 };
  const cursorXSpring = useSpring(cursorX, springConfig);
  const cursorYSpring = useSpring(cursorY, springConfig);
  const [isHovering, setIsHovering] = useState(false);

  useEffect(() => {
    if (isTouch || reduceMotion) return;
    const move = (e: MouseEvent) => {
      cursorX.set(e.clientX - 16);
      cursorY.set(e.clientY - 16);
    };
    const over = (e: MouseEvent) =>
      setIsHovering(
        (e.target as HTMLElement)?.closest("a, button, [data-cursor-hover]") != null,
      );
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseover", over, true);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseover", over, true);
    };
  }, [isTouch, reduceMotion, cursorX, cursorY]);

  if (isTouch || reduceMotion) return null;

  return (
    <>
      <motion.div
        aria-hidden
        className="pointer-events-none fixed left-0 top-0 z-[80] h-8 w-8 rounded-full border border-white/40 mix-blend-difference"
        style={{ x: cursorXSpring, y: cursorYSpring, scale: isHovering ? 2.5 : 1 }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none fixed left-0 top-0 z-[79] h-2 w-2 rounded-full bg-white"
        style={{ x: cursorX, y: cursorY }}
      />
    </>
  );
}

function MagneticButton({
  children,
  className = "",
  href,
}: {
  children: ReactNode;
  className?: string;
  href: string;
}) {
  const ref = useRef<HTMLAnchorElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 300, damping: 20 });
  const springY = useSpring(y, { stiffness: 300, damping: 20 });

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    x.set((e.clientX - rect.left - rect.width / 2) * 0.3);
    y.set((e.clientY - rect.top - rect.height / 2) * 0.3);
  };
  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  return (
    <motion.div style={{ x: springX, y: springY }} className="inline-block">
      <Button asChild className={className}>
        <Link
          ref={ref}
          href={href}
          data-cursor-hover
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {children}
        </Link>
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
      className="overflow-hidden border-y border-white/10 bg-black/20 py-3 backdrop-blur-sm"
    >
      <motion.div
        className="flex gap-12 whitespace-nowrap text-xs uppercase tracking-[0.2em] text-white/50"
        animate={paused ? undefined : { x: ["0%", "-50%"] }}
        transition={paused ? undefined : { repeat: Infinity, duration: 30, ease: "linear" }}
      >
        {[...items, ...items].map((item, i) => (
          <span key={`${item}-${i}`} className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500/50" />
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

  return (
    <motion.div
      className="relative h-full min-h-[280px] w-full sm:min-h-[360px] lg:min-h-[60vh]"
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
    >
      <Image
        src="/assets/hero-poster.webp"
        alt=""
        width={1200}
        height={800}
        priority
        aria-hidden
        className={`absolute inset-0 mx-auto h-full w-[115%] max-w-none object-contain drop-shadow-[0_120px_240px_rgba(0,0,0,0.35)] transition-opacity duration-700 sm:w-[120%] lg:w-[140%] ${
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
          poster="/assets/hero-poster.webp"
          className={`absolute inset-0 h-full w-full object-contain transition-opacity duration-700 ${
            videoReady ? "opacity-100" : "opacity-0"
          }`}
          onCanPlay={() => setVideoReady(true)}
        >
          <source src="/assets/hero.webm" type="video/webm" />
          <source src="/assets/hero.mp4" type="video/mp4" />
        </video>
      )}
    </motion.div>
  );
}

export function HomeLanding() {
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const heroScale = useTransform(scrollYProgress, [0, 0.2], reduceMotion ? [1, 1] : [1.08, 1]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.15], [1, 0.9]);

  return (
    <div className="relative overflow-x-hidden bg-[#0a0a0c] text-white selection:bg-emerald-500/30">
      <CustomCursor />
      <NoiseOverlay />

      <motion.div
        style={{ scaleX: scrollYProgress }}
        className="fixed top-0 left-0 z-50 h-px w-full origin-left bg-gradient-to-r from-emerald-400 to-cyan-300"
        aria-hidden
      />

      <section className="relative flex min-h-[calc(100vh-4rem)] items-center overflow-hidden pt-8 sm:pt-12 lg:min-h-screen lg:pt-0">
        <motion.div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-br from-slate-900/50 via-[#0a0a0c] to-emerald-950/30"
        />

        <motion.div className="relative z-10 mx-auto w-full max-w-7xl px-6">
          <motion.div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <motion.div
              initial={reduceMotion ? false : { opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs tracking-[0.2em] text-emerald-400">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                {LOGO}
              </div>

              <h1 className="mt-6 text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-7xl">
                Автомобили из Азии
                <span className="mt-2 block bg-gradient-to-r from-emerald-400 to-cyan-300 bg-clip-text text-transparent">
                  как новый стандарт качества
                </span>
              </h1>

              <p className="mt-6 max-w-lg text-lg text-white/70">
                Подбор, проверка и доставка автомобилей без посредников
              </p>

              <div className="mt-10 flex flex-wrap gap-4">
                <MagneticButton
                  href="/catalog"
                  className="h-12 rounded-full bg-white px-8 font-medium text-black hover:bg-white/90"
                >
                  Каталог
                </MagneticButton>
                <MagneticButton
                  href="/contacts"
                  className="h-12 rounded-full border border-white/20 px-8 font-medium hover:bg-white/10"
                >
                  Обсудить
                </MagneticButton>
              </div>

              <motion.div
                className="mt-10 flex flex-wrap gap-3"
                initial={reduceMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.35, duration: 0.6 }}
              >
                {["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка", "Экспорт"].map((badge) => (
                  <span
                    key={badge}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white/70"
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

      <section className="bg-[#0f0f12] py-16 sm:py-20" aria-label="Статистика">
        <div className="mx-auto grid max-w-7xl grid-cols-2 gap-8 px-6 lg:grid-cols-4">
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={reduceMotion ? false : { opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="text-center"
            >
              <div className="text-3xl font-bold text-white lg:text-4xl">
                <AnimatedNumber value={stat.value} suffix={stat.suffix} />
              </div>
              <div className="mt-2 text-sm text-white/60">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="py-20 sm:py-28">
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 lg:grid-cols-2">
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
          >
            <p className="text-xs uppercase tracking-[0.3em] text-emerald-400">Контроль качества</p>
            <h2 className="mt-4 text-3xl font-bold sm:text-4xl lg:text-5xl">Проверка до покупки</h2>
            <p className="mt-6 text-lg text-white/70">
              Фото, видео и диагностика каждого автомобиля перед сделкой
            </p>
            <ul className="mt-6 space-y-3 text-white/70">
              {["HD-фото 360°", "Видеоосмотр в реальном времени", "Технический аудит", "Проверка истории"].map(
                (item) => (
                  <li key={item} className="flex items-center gap-3">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    {item}
                  </li>
                ),
              )}
            </ul>
          </motion.div>

          <motion.div
            initial={reduceMotion ? false : { opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="overflow-hidden rounded-3xl border border-white/10 bg-white/5"
          >
            <Image
              src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1800&q=80"
              alt="Осмотр автомобиля перед покупкой"
              width={1800}
              height={1000}
              className="h-full w-full object-cover"
            />
          </motion.div>
        </div>
      </section>

      <section className="bg-[#0f0f12] py-20 sm:py-28">
        <motion.div className="mx-auto grid max-w-7xl items-center gap-12 px-6 lg:grid-cols-2">
          <motion.div
            initial={reduceMotion ? false : { opacity: 0, x: -30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="order-2 overflow-hidden rounded-3xl border border-white/10 lg:order-1"
          >
            <Image
              src="https://images.unsplash.com/photo-1619767886558-efdc259cde1a?auto=format&fit=crop&w=1800&q=80"
              alt="Японский автомобильный аукцион"
              width={1800}
              height={1000}
              className="h-full w-full object-cover"
            />
          </motion.div>

          <motion.div
            initial={reduceMotion ? false : { opacity: 0, x: 30 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="order-1 lg:order-2"
          >
            <p className="text-xs uppercase tracking-[0.3em] text-emerald-400">Источник авто</p>
            <h2 className="mt-4 text-3xl font-bold sm:text-4xl lg:text-5xl">Прямой доступ к аукционам</h2>
            <p className="mt-6 text-lg text-white/70">
              Работаем без посредников и скрытых наценок — USS, TAA, AUCNET и площадки Кореи и Китая
            </p>
          </motion.div>
        </motion.div>
      </section>

      <section className="py-20 sm:py-28" aria-label="Процесс">
        <div className="mx-auto max-w-7xl px-6">
          <motion.h2
            className="text-3xl font-bold sm:text-4xl lg:text-5xl"
            initial={reduceMotion ? false : { opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            Процесс
          </motion.h2>
          <div className="mt-12 grid grid-cols-2 gap-8 sm:gap-10 lg:grid-cols-4">
            {PROCESS_STEPS.map(([n, t], i) => (
              <motion.div
                key={n}
                initial={reduceMotion ? false : { opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
              >
                <div className="text-4xl text-white/15 sm:text-5xl">{n}</div>
                <div className="mt-3 text-lg font-medium sm:text-xl">{t}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-gradient-to-b from-[#0a0a0c] to-black py-24 sm:py-32">
        <motion.div
          className="mx-auto max-w-3xl px-6 text-center"
          initial={reduceMotion ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-3xl font-bold sm:text-4xl lg:text-6xl">Найдём автомобиль под вас</h2>
          <p className="mt-6 text-lg text-white/60">Полный цикл под ключ — без посредников</p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <MagneticButton
              href="/catalog"
              className="h-12 rounded-full bg-white px-8 font-medium text-black hover:bg-white/90"
            >
              Подобрать авто
            </MagneticButton>
            <MagneticButton
              href="https://t.me/nikits15"
              className="h-12 rounded-full border border-white/20 bg-white/5 px-8 font-medium hover:bg-white/10"
            >
              Telegram
            </MagneticButton>
          </div>
        </motion.div>
      </section>
    </div>
  );
}
