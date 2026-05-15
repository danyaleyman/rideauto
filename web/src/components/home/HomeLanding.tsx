import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Car, FileText, Globe2, Headphones, MapPin, Play, Sparkles, Video, Warehouse } from "lucide-react";
import { HomeTrustStrip } from "@/components/home/HomeTrustStrip";

const HERO_IMAGE = "/assets/landing-main-page.png";
const VIDEO_REPORTS_URL = "/assets/Check-preview.png";
const TELEGRAM_URL = "https://t.me/nikits15";

export function HomeLanding() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* HERO */}
      <section className="relative overflow-hidden bg-[#050505] pb-24 pt-16 text-white lg:pt-24">
        {/* glow background */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 right-[-10%] h-[500px] w-[500px] rounded-full bg-primary/20 blur-[120px]" />
          <div className="absolute bottom-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-blue-500/10 blur-[140px]" />
        </div>

        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-6 lg:grid-cols-[1fr_1.2fr]">
          {/* LEFT */}
          <div className="relative z-10 max-w-xl">
            <p className="text-xs uppercase tracking-[0.3em] text-white/50">
              Ride Auto
            </p>

            <h1 className="mt-6 text-5xl font-semibold leading-[0.9] tracking-tight text-white sm:text-6xl lg:text-7xl xl:text-[92px]">
              Автомобили
              <br />
              из Азии —
              <br />
              без сложностей
            </h1>

            <p className="mt-6 max-w-md text-lg leading-relaxed text-white/60">
              Подбор, проверка и доставка автомобилей из Кореи, Китая и Японии под ключ.
            </p>

            <div className="mt-10 flex flex-wrap gap-3">
              <Button asChild size="lg" className="h-12 rounded-full px-8 text-base">
                <Link href="/catalog">Каталог</Link>
              </Button>

              <Button
                asChild
                size="lg"
                variant="secondary"
                className="h-12 rounded-full border border-white/10 bg-white/10 px-8 text-white backdrop-blur hover:bg-white/15"
              >
                <Link href="/contacts">Консультация</Link>
              </Button>

              <Button
                asChild
                size="lg"
                variant="ghost"
                className="h-12 rounded-full px-8 text-white hover:bg-white/10"
              >
                <a href={TELEGRAM_URL} target="_blank" rel="noopener noreferrer">
                  Telegram
                </a>
              </Button>
            </div>
          </div>

          {/* RIGHT IMAGE */}
          <div className="relative">
            <div className="absolute inset-0 scale-110 bg-primary/20 blur-[120px]" />

            <Image
              src={HERO_IMAGE}
              alt="Ride Auto Car"
              width={1400}
              height={900}
              priority
              className="relative z-10 object-contain drop-shadow-[0_60px_140px_rgba(0,0,0,0.55)] transition-transform duration-700 hover:scale-[1.02]"
            />
          </div>
        </div>
      </section>

      {/* TRUST STRIP - companies/regions */}
      <section className="border-y border-white/10 bg-[#050505] py-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 text-sm text-white/45">
          <span>Китай</span>
          <span>Корея</span>
          <span>Япония</span>
          <span>Видеоосмотр</span>
          <span>Доставка под ключ</span>
          <span>Экспорт</span>
        </div>
      </section>

      {/* FEATURE SECTION - Вы видите автомобиль до покупки */}
      <section className="mx-auto max-w-6xl px-6 py-32">
        <div className="grid gap-16 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-muted-foreground">
              Контроль качества
            </p>
            <h2 className="mt-4 text-4xl font-semibold tracking-tight lg:text-5xl">
              Вы видите автомобиль
              <br />
              до покупки
            </h2>
            <p className="mt-6 text-lg text-muted-foreground">
              Фото, видео и полная диагностика перед выкупом.
            </p>
            <div className="mt-8">
              <a
                href={VIDEO_REPORTS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-primary hover:underline"
              >
                Примеры отчётов
                <ArrowRight className="h-4 w-4" />
              </a>
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[32px] border border-border/60 shadow-[0_20px_60px_rgba(0,0,0,0.08)]">
            <Image
              src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1400&q=80"
              alt="Осмотр автомобиля"
              width={1200}
              height={900}
              className="object-cover transition duration-700 hover:scale-[1.03]"
            />
          </div>
        </div>
      </section>

      {/* ADVANTAGES - быстрые преимущества */}
      <section className="mx-auto max-w-6xl px-6 py-32 border-t border-border/60">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-semibold tracking-tight lg:text-5xl">
            Работаем без посредников
          </h2>
          <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
            Полная прозрачность на каждом этапе
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: Car, title: "Каталог авто", desc: "Фильтры по рынку, цене и характеристикам — Китай и Корея в одном интерфейсе." },
            { icon: Video, title: "Видеоотчёты", desc: "Фото и видео с площадки, чтобы принять решение дистанционно." },
            { icon: Globe2, title: "Доставка", desc: "Экспортируем в любую страну — привезём куда нужно." },
            { icon: Sparkles, title: "С 2021 года", desc: "Опыт подбора из Азии и сопровождения сделок." },
          ].map(({ icon: Icon, title, desc }) => (
            <div key={title} className="rounded-2xl border border-border/60 bg-card/40 p-6 backdrop-blur-sm transition hover:-translate-y-1 hover:shadow-lg">
              <Icon className="h-8 w-8 text-primary" />
              <h3 className="mt-4 text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* PROCESS - Как проходит покупка */}
      <section className="mx-auto max-w-6xl px-6 py-32 border-t border-border/60">
        <h2 className="text-4xl font-semibold tracking-tight lg:text-5xl">
          Как проходит покупка
        </h2>

        <div className="mt-16 grid gap-12 border-t border-border/60 pt-12 lg:grid-cols-4">
          {[
            ["01", "Подбор", "Находим авто под бюджет и запрос"],
            ["02", "Проверка", "Видеоосмотр и диагностика"],
            ["03", "Выкуп", "Оформление и экспорт"],
            ["04", "Доставка", "Привозим и передаём авто"],
          ].map(([n, t, d]) => (
            <div key={n}>
              <div className="text-6xl font-semibold tracking-tight text-muted-foreground/40">
                {n}
              </div>
              <h3 className="mt-4 text-xl font-medium">{t}</h3>
              <p className="mt-2 text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* VIDEO REPORTS SECTION */}
      <section className="mx-auto max-w-6xl px-6 py-32 border-t border-border/60">
        <h2 className="text-4xl font-semibold">Видеоотчёты</h2>
        <p className="mt-4 text-muted-foreground">
          Подробная проверка каждого автомобиля перед покупкой
        </p>

        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {[
            ["Volvo XC90", VIDEO_REPORTS_URL, "https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=800&q=80"],
            ["Kia Sorento", VIDEO_REPORTS_URL, "https://images.unsplash.com/photo-1486262715619-067b786738f6?auto=format&fit=crop&w=800&q=80"],
            ["Заказать осмотр", "/contacts", "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=800&q=80"],
          ].map(([t, href, img]) => (
            <Link
              key={t}
              href={href}
              target={href.startsWith("http") ? "_blank" : undefined}
              rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
              className="group overflow-hidden rounded-[28px] border border-border/60 bg-card/40 backdrop-blur-sm transition duration-300 hover:-translate-y-1 hover:shadow-2xl"
            >
              <div className="relative aspect-video">
                <Image
                  src={img}
                  alt={t}
                  fill
                  className="object-cover transition duration-500 group-hover:scale-[1.04]"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition group-hover:opacity-100">
                  <Play className="h-12 w-12 text-white drop-shadow-lg" />
                </div>
              </div>
              <div className="flex items-center justify-between p-4">
                <span className="font-medium">{t}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-1" />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* PERSONAL MANAGER BLOCK */}
      <section className="mx-auto max-w-6xl px-6 py-32 border-t border-border/60">
        <div className="flex flex-col gap-8 overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-br from-muted/50 via-card to-card p-8 shadow-lg sm:flex-row sm:items-center sm:justify-between lg:p-10">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs font-medium">
              <Headphones className="h-3.5 w-3.5 text-primary" />
              Сопровождение сделки
            </div>
            <h3 className="mt-4 text-2xl font-semibold tracking-tight sm:text-3xl">
              Курируем автомобиль до получения
            </h3>
            <p className="mt-2 text-muted-foreground">
              Ваш личный менеджер остаётся на связи до получения вами автомобиля.
              Отвечает на все вопросы, при необходимости, даже ночью.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild size="lg" className="rounded-full">
                <Link href="/contacts">Связаться</Link>
              </Button>
              <Button variant="outline" asChild size="lg" className="rounded-full">
                <Link href="/buy">Как купить</Link>
              </Button>
            </div>
          </div>
          <div className="flex h-32 w-32 items-center justify-center rounded-2xl bg-primary/10">
            <Headphones className="h-14 w-14 text-primary" />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden bg-[#050505] px-6 py-32 text-white">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.12),transparent_40%)]" />

        <div className="relative mx-auto max-w-3xl text-center">
          <h2 className="text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            Найдём автомобиль,
            <br />
            который подойдёт вам
          </h2>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild className="h-12 rounded-full px-8 text-base">
              <Link href="/catalog">Подобрать авто</Link>
            </Button>
            <Button
              asChild
              variant="secondary"
              className="h-12 rounded-full border border-white/10 bg-white/10 px-8 text-white backdrop-blur hover:bg-white/15"
            >
              <a href={TELEGRAM_URL} target="_blank" rel="noopener noreferrer">
                Telegram
              </a>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}