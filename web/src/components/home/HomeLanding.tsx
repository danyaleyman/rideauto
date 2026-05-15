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
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Sparkles, Camera, Settings, Shield, Truck } from "lucide-react";

const CAR = "/assets/landing-main-page.png";

const COLORS = [
  "0deg",   // neutral
  "15deg",  // warm
  "30deg",  // gold-ish
  "-10deg", // cool tone
];

const HOTSPOTS = [
  { id: "lights", label: "Матричные фары", x: "20%", y: "35%", description: "Полностью светодиодная оптика с автоматической регулировкой" },
  { id: "wheels", label: "Легкосплавные диски", x: "75%", y: "65%", description: "19\" диски с низкопрофильной резиной" },
  { id: "mirror", label: "Камера 360°", x: "85%", y: "30%", description: "Круговой обзор с парковочными ассистентами" },
];

export function HomeLanding() {
  const ref = useRef(null);
  const [activeSpot, setActiveSpot] = useState<string | null>(null);
  const [mode, setMode] = useState<"exterior" | "interior">("exterior");

  const { scrollYProgress, scrollY } = useScroll({
    target: ref,
    offset: ["start start", "end end"]
  });

  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    mass: 0.5,
  });

  // camera system
  const rotateX = useTransform(scrollY, [0, 1500], [0, -8]);
  const rotateY = useTransform(scrollY, [0, 1500], [0, 12]);
  const scale = useTransform(scrollY, [0, 1500], [1.2, 0.95]);
  const opacity = useTransform(scrollY, [0, 800], [1, 0.4]);
  const colorShift = useTransform(scrollY, [0, 1500], COLORS);

  // звуки (заглушка)
  const playSound = (type: string) => {
    console.log("🔊 sound:", type);
  };

  useEffect(() => {
    playSound(mode === "interior" ? "interior_view" : "exterior_view");
  }, [mode]);

  return (
    <div ref={ref} className="relative bg-background">
      
      {/* прогресс бар */}
      <motion.div
        style={{ scaleX: smoothProgress }}
        className="fixed left-0 top-0 z-50 h-[2px] w-full origin-left bg-primary"
      />

      {/* ================= HERO СЦЕНА ================= */}
      <section className="relative min-h-[250vh]">
        
        {/* sticky camera */}
        <div className="sticky top-0 h-screen overflow-hidden">
          
          {/* эффекты освещения */}
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -top-40 right-[-20%] h-[800px] w-[800px] rounded-full bg-primary/15 blur-[200px]" />
            <div className="absolute bottom-[-30%] left-[-10%] h-[600px] w-[600px] rounded-full bg-blue-500/5 blur-[180px]" />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-background/40" />
          </div>

          {/* переключатель режимов */}
          <div className="fixed left-1/2 top-6 z-30 flex -translate-x-1/2 gap-2 rounded-full border border-border/60 bg-background/80 p-1 backdrop-blur-md shadow-lg">
            <button
              onClick={() => setMode("exterior")}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-all ${
                mode === "exterior"
                  ? "bg-primary text-primary-foreground shadow-md"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Экстерьер
            </button>
            <button
              onClick={() => setMode("interior")}
              className={`rounded-full px-5 py-2 text-sm font-medium transition-all ${
                mode === "interior"
                  ? "bg-primary text-primary-foreground shadow-md"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Интерьер
            </button>
          </div>

          {/* 3D объект — автомобиль */}
          <motion.div
            style={{
              scale,
              rotateX,
              rotateY,
              opacity,
              filter: `hue-rotate(${colorShift.get?.() ?? "0deg"})`,
            }}
            className="absolute inset-0 flex items-center justify-center"
            transition={{ type: "spring", stiffness: 100, damping: 20 }}
          >
            <div className="relative w-full max-w-[1400px]">
              
              <Image
                src={CAR}
                alt="Premium автомобиль из Азии"
                width={2600}
                height={1600}
                priority
                className="w-full object-contain drop-shadow-[0_100px_200px_rgba(0,0,0,0.4)]"
              />

              {/* интерактивные точки — экстерьер */}
              {mode === "exterior" && (
                <div className="absolute inset-0">
                  {HOTSPOTS.map((spot) => (
                    <motion.div
                      key={spot.id}
                      initial={{ scale: 0, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      transition={{ delay: 0.5 }}
                      style={{ left: spot.x, top: spot.y }}
                      className="absolute"
                      onMouseEnter={() => setActiveSpot(spot.id)}
                      onMouseLeave={() => setActiveSpot(null)}
                    >
                      <div className="relative cursor-pointer">
                        {/* пульсирующая точка */}
                        <div className="absolute inset-0 animate-ping rounded-full bg-primary/60" />
                        <div className="relative h-3 w-3 rounded-full bg-primary shadow-lg" />
                      </div>
                      
                      {/* подсказка */}
                      {activeSpot === spot.id && (
                        <motion.div
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          className="absolute left-6 top-0 z-20 w-48 rounded-lg bg-background/95 p-2 text-xs shadow-lg border border-border/60 backdrop-blur"
                        >
                          <p className="font-semibold text-foreground">{spot.label}</p>
                          <p className="mt-0.5 text-muted-foreground">{spot.description}</p>
                        </motion.div>
                      )}
                    </motion.div>
                  ))}
                </div>
              )}

              {/* интерьер — оверлей */}
              {mode === "interior" && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="absolute inset-0 flex items-center justify-center bg-black/40 backdrop-blur-sm rounded-2xl mx-20"
                >
                  <div className="text-center text-white">
                    <p className="text-lg font-medium">Премиальный салон</p>
                    <p className="mt-2 text-sm text-white/70">Кожа Nappa • Вентиляция • Массаж • Премиум аудио</p>
                    <Button variant="secondary" size="sm" className="mt-4 rounded-full" asChild>
                      <Link href="/catalog/cars">Смотреть в каталоге</Link>
                    </Button>
                  </div>
                </motion.div>
              )}

            </div>
          </motion.div>

          {/* HUD — индикатор скролла */}
          <motion.div 
            style={{ opacity: useTransform(scrollY, [0, 500], [1, 0]) }}
            className="absolute bottom-8 left-1/2 z-20 -translate-x-1/2 text-center"
          >
            <p className="text-xs text-muted-foreground">Скролл для просмотра</p>
            <div className="mt-2 flex justify-center">
              <div className="h-10 w-5 rounded-full border border-border/60 p-1">
                <motion.div
                  animate={{ y: [0, 12, 0] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  className="h-2 w-2 rounded-full bg-primary mx-auto"
                />
              </div>
            </div>
          </motion.div>

          {/* уголок с информацией */}
          <motion.div 
            style={{ opacity: useTransform(scrollY, [0, 300], [1, 0]) }}
            className="absolute right-6 bottom-24 z-20 max-w-sm text-right"
          >
            <p className="text-sm text-muted-foreground">
              {mode === "exterior" ? "• Динамичный дизайн" : "• Премиальный салон"}
              <br />
              {mode === "exterior" ? "• Аэродинамический профиль" : "• Комфорт премиум класса"}
            </p>
          </motion.div>

        </div>
      </section>

      {/* ================= INFO — КОНТРОЛЬ КАЧЕСТВА ================= */}
      <section className="relative min-h-screen flex items-center px-6 bg-gradient-to-b from-background via-background to-muted/20">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-primary font-medium">Контроль качества</p>
              <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
                Полная инженерная проверка
              </h2>
              <p className="mt-6 text-base text-muted-foreground leading-relaxed">
                Каждый автомобиль проходит многоступенчатую диагностику всех узлов и агрегатов.
                Мы фиксируем все на фото и видео — вы видите машину до покупки.
              </p>
              <div className="mt-8 flex flex-wrap gap-4">
                <div className="flex items-center gap-2">
                  <Camera className="h-4 w-4 text-primary" />
                  <span className="text-sm">Фотоотчёт</span>
                </div>
                <div className="flex items-center gap-2">
                  <Settings className="h-4 w-4 text-primary" />
                  <span className="text-sm">Диагностика</span>
                </div>
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary" />
                  <span className="text-sm">Гарантия</span>
                </div>
              </div>
              <Button variant="outline" className="mt-8 rounded-full" asChild>
                <Link href="/reports">
                  Смотреть примеры отчётов
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
            <div className="relative overflow-hidden rounded-2xl border border-border/60 shadow-xl">
              <Image
                src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1400&q=80"
                alt="Осмотр автомобиля"
                width={800}
                height={600}
                className="object-cover"
              />
            </div>
          </div>
        </div>
      </section>

      {/* ================= ПРОЦЕСС ПОКУПКИ ================= */}
      <section className="min-h-screen flex items-center px-6 py-24">
        <div className="mx-auto w-full max-w-6xl">
          <div className="text-center">
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
              Как проходит покупка
            </h2>
            <p className="mt-4 text-muted-foreground">Прозрачно и без посредников</p>
          </div>

          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { num: "01", title: "Подбор", desc: "Анализируем рынок под ваш бюджет", icon: Sparkles },
              { num: "02", title: "Проверка", desc: "Видеоосмотр и диагностика", icon: Camera },
              { num: "03", title: "Выкуп", desc: "Оформление сделки и экспорт", icon: Shield },
              { num: "04", title: "Доставка", desc: "Передача автомобиля вам", icon: Truck },
            ].map((item, idx) => (
              <motion.div
                key={item.num}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: idx * 0.1 }}
                className="group text-center"
              >
                <div className="flex justify-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 text-2xl font-bold text-primary">
                    {item.num}
                  </div>
                </div>
                <h3 className="mt-4 text-xl font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ================= CTA ================= */}
      <section className="relative min-h-[70vh] flex items-center px-6 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/20 via-primary/5 to-background" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.1),transparent_60%)]" />
        
        <div className="relative mx-auto max-w-3xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl lg:text-5xl">
              Найдём автомобиль,
              <br />
              который вам подходит
            </h2>
            <p className="mt-4 text-muted-foreground">
              Оставьте заявку — мы подберём варианты под ваш бюджет
            </p>
            <div className="mt-10 flex flex-wrap justify-center gap-3">
              <Button asChild size="lg" className="rounded-full px-8 shadow-lg">
                <Link href="/catalog">Подобрать авто</Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="rounded-full px-8">
                <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                  Написать в Telegram
                </a>
              </Button>
            </div>
            <p className="mt-6 text-xs text-muted-foreground">
              Бесплатная консультация • Отвечаем за 15 минут
            </p>
          </motion.div>
        </div>
      </section>

    </div>
  );
}