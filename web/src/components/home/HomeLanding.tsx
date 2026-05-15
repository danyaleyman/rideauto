import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight, Play } from "lucide-react";

const HERO_IMAGE = "/assets/landing-main-page.png";

// TODO: replace with real assets (car showroom / hero cinematic)
const TRUST_ITEMS = ["Китай", "Корея", "Япония", "Видеоосмотр", "Доставка под ключ", "Экспорт"];

export function HomeLanding() {
  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* HERO (theme-aware: dark overlay but respects system theme base) */}
      <section className="relative overflow-hidden bg-background text-foreground">
        {/* cinematic glow */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-40 right-[-10%] h-[500px] w-[500px] rounded-full bg-primary/20 blur-[120px]" />
          <div className="absolute bottom-[-20%] left-[-10%] h-[500px] w-[500px] rounded-full bg-blue-500/10 blur-[140px]" />
        </div>

        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 px-6 py-20 lg:grid-cols-[0.95fr_1.2fr] lg:py-28">

          {/* LEFT */}
          <div className="relative z-10 max-w-xl">
            <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
              Ride Auto
            </p>

            <h1 className="mt-6 text-5xl font-semibold leading-[0.95] tracking-tight sm:text-6xl lg:text-7xl">
              Автомобили
              <br />
              из Азии —
              <br />
              без сложностей
            </h1>

            <p className="mt-6 max-w-md text-lg leading-relaxed text-muted-foreground">
              Подбор, проверка и доставка автомобилей из Кореи, Китая и Японии под ключ.
            </p>

            <div className="mt-10 flex flex-wrap gap-3">
              <Button asChild size="lg" className="h-12 rounded-full px-8 text-base">
                <Link href="/catalog">Каталог</Link>
              </Button>

              <Button asChild size="lg" variant="secondary" className="h-12 rounded-full px-8">
                <Link href="/contacts">Консультация</Link>
              </Button>
            </div>
          </div>

          {/* RIGHT IMAGE */}
          <div className="relative">
            {/* glow behind image */}
            <div className="absolute inset-0 scale-110 bg-primary/10 blur-[120px]" />

            {/* PLACEHOLDER NOTE: swap with cinematic car render (side/front angle) */}
            <Image
              src={HERO_IMAGE}
              alt="Ride Auto Hero Car"
              width={1400}
              height={900}
              priority
              className="relative z-10 object-contain drop-shadow-[0_60px_140px_rgba(0,0,0,0.35)] transition-transform duration-700 hover:scale-[1.02]"
            />
          </div>
        </div>
      </section>

      {/* TRUST STRIP */}
      <section className="border-y border-border/60 bg-background/60 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-6 py-6 text-sm text-muted-foreground">
          {TRUST_ITEMS.map((item) => (
            <span key={item} className="tracking-wide">
              {item}
            </span>
          ))}
        </div>
      </section>

      {/* FEATURE HERO BLOCK (editorial style, not card-based) */}
      <section className="mx-auto max-w-6xl px-6 py-28 lg:py-40">
        <div className="grid gap-14 lg:grid-cols-2 lg:items-center">
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
              Фото, видео и диагностика перед выкупом — дистанционное принятие решения.
            </p>

            <div className="mt-8 text-sm text-primary">
              <Link href="/reports" className="inline-flex items-center gap-2 hover:underline">
                Примеры отчётов
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          {/* PLACEHOLDER IMAGE */}
          <div className="relative overflow-hidden rounded-[32px] border border-border/60 bg-muted">
            <Image
              src="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=1400&q=80"
              alt="Car inspection"
              width={1200}
              height={900}
              className="object-cover transition duration-700 hover:scale-[1.03]"
            />
          </div>
        </div>
      </section>

      {/* PROCESS (minimal + premium spacing) */}
      <section className="mx-auto max-w-6xl px-6 py-28 lg:py-40">
        <h2 className="text-4xl font-semibold tracking-tight lg:text-5xl">
          Как проходит покупка
        </h2>

        <div className="mt-16 grid gap-14 lg:grid-cols-4">
          {[
            ["01", "Подбор", "Находим авто под бюджет и запрос"],
            ["02", "Проверка", "Видеоосмотр и диагностика"],
            ["03", "Выкуп", "Оформление и экспорт"],
            ["04", "Доставка", "Передача автомобиля клиенту"],
          ].map(([n, t, d]) => (
            <div key={n}>
              <div className="text-6xl font-semibold tracking-tight text-muted-foreground/30">
                {n}
              </div>
              <h3 className="mt-4 text-xl font-medium">{t}</h3>
              <p className="mt-2 text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* VIDEO (needs real thumbnails later) */}
      <section className="mx-auto max-w-6xl px-6 py-28 lg:py-40">
        <h2 className="text-4xl font-semibold">Видеоотчёты</h2>
        <p className="mt-4 text-muted-foreground">
          Полная проверка автомобиля перед покупкой
        </p>

        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {[
            ["Volvo XC90", "https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=800&q=80"],
            ["Kia Sorento", "https://images.unsplash.com/photo-1486262715619-067b786738f6?auto=format&fit=crop&w=800&q=80"],
            ["Заказать осмотр", "/contacts"],
          ].map(([t, img]) => (
            <Link
              key={t}
              href="#"
              className="group overflow-hidden rounded-[28px] border border-border/60 bg-card/40 transition hover:-translate-y-1 hover:shadow-2xl"
            >
              <div className="relative aspect-video bg-muted">
                {img ? (
                  <Image
                    src={img as string}
                    alt={t}
                    fill
                    className="object-cover transition duration-500 group-hover:scale-[1.04]"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    Placeholder image
                  </div>
                )}

                <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition group-hover:opacity-100">
                  <Play className="h-12 w-12 text-white" />
                </div>
              </div>

              <div className="flex items-center justify-between p-4">
                <span className="font-medium">{t}</span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* CTA (theme-aware, no hard black dependency) */}
      <section className="relative overflow-hidden bg-primary text-primary-foreground">
        <div className="absolute inset-0 opacity-10 bg-[radial-gradient(circle_at_top,white,transparent_60%)]" />

        <div className="relative mx-auto max-w-3xl px-6 py-28 text-center lg:py-40">
          <h2 className="text-4xl font-semibold leading-tight sm:text-5xl">
            Найдём автомобиль,
            <br />
            который подойдёт вам
          </h2>

          <div className="mt-10 flex flex-wrap justify-center gap-3">
            <Button asChild size="lg" className="h-12 rounded-full px-8">
              <Link href="/catalog">Подобрать авто</Link>
            </Button>

            <Button asChild size="lg" variant="secondary" className="h-12 rounded-full px-8">
              <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                Telegram
              </a>
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}