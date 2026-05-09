import type { ComponentType, ReactNode } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  Car,
  FileText,
  Globe2,
  Headphones,
  MapPin,
  Play,
  Sparkles,
  Video,
  Warehouse,
} from "lucide-react";
import { HomeTrustStrip } from "@/components/home/HomeTrustStrip";
import { MotionFadeUp, MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Подборочное фото для героя (Unsplash, разрешено в `next.config` remotePatterns). */
const HERO_IMAGE =
  "https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&w=1600&q=80";

const VIDEO_REPORTS_URL = "https://disk.yandex.ru/d/RYB3Xyk8sNQUZQ";
const TELEGRAM_URL = "https://t.me/nikits15";

function SectionHeading({
  title,
  subtitle,
  className,
}: {
  title: string;
  subtitle?: string;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto max-w-3xl text-center", className)}>
      <h2 className="text-balance text-2xl font-semibold tracking-tight text-foreground sm:text-3xl lg:text-4xl">
        {title}
      </h2>
      {subtitle ? (
        <p className="mt-3 text-pretty text-base leading-relaxed text-muted-foreground sm:text-lg">
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}

function FeatureTile({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "group flex min-h-full flex-col rounded-2xl border border-border/60 bg-card/80 p-4 shadow-sm ring-1 ring-elevated-ring backdrop-blur-sm transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md sm:p-5",
        className,
      )}
    >
      <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <h3 className="text-sm font-semibold leading-snug text-foreground sm:text-base">{title}</h3>
      <div className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </div>
  );
}

function VideoThumbCard({
  href,
  label,
  thumbSrc,
  thumbAlt,
}: {
  href: string;
  label: string;
  thumbSrc: string;
  thumbAlt: string;
}) {
  const isExternal = /^https?:\/\//.test(href);
  const className =
    "group block overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm ring-1 ring-elevated-ring transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md";

  const inner = (
    <>
      <div className="relative aspect-video overflow-hidden bg-muted">
        <Image
          src={thumbSrc}
          alt={thumbAlt}
          fill
          className="object-cover transition duration-300 group-hover:scale-[1.03]"
          sizes="(max-width: 768px) 100vw, 33vw"
        />
        <span className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" aria-hidden />
        <span className="absolute left-1/2 top-1/2 flex h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-background/90 text-foreground shadow-md ring-1 ring-border/60 transition group-hover:scale-105">
          <Play className="h-5 w-5 fill-current" aria-hidden />
        </span>
      </div>
      <p className="flex items-center justify-center gap-1 px-3 py-3 text-sm font-medium text-foreground">
        {label}
        <ArrowRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5" aria-hidden />
      </p>
    </>
  );

  if (isExternal) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
        {inner}
      </a>
    );
  }

  return (
    <Link href={href} className={className}>
      {inner}
    </Link>
  );
}

export function HomeLanding() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-gradient-to-b from-muted/35 via-background to-background pb-12 pt-2 sm:pt-4">
      <div className="relative mx-auto min-w-0 max-w-[1440px] px-3 sm:px-6 lg:px-10">
        {/* Hero */}
        <MotionFadeUp>
          <section className="relative overflow-hidden rounded-3xl border border-border/50 bg-card/60 shadow-sm ring-1 ring-elevated-ring backdrop-blur-sm">
            <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:items-center lg:gap-10 lg:p-10 xl:p-12">
              <div className="relative z-10 min-w-0">
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary sm:text-sm">
                  World Ride Auto
                </p>
                <h1 className="mt-3 text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl lg:text-5xl">
                  Автомобиль из Азии под ключ
                </h1>
                <p className="mt-3 text-pretty text-lg text-muted-foreground sm:text-xl">
                  Корея, Китай и Япония — подбор, проверка и доставка во Владивосток
                </p>
                <p className="mt-4 max-w-xl text-pretty text-sm leading-relaxed text-muted-foreground sm:text-base">
                  Подбираем и везём автомобили с площадок и аукционов. Сопровождаем от заявки до таможни и
                  вручения: прозрачные этапы и понятная коммуникация.
                </p>
                <div className="mt-7 flex min-w-0 flex-col gap-3 sm:flex-row sm:flex-wrap">
                  <Button className="w-full rounded-2xl sm:w-auto" size="lg" asChild>
                    <Link href="/catalog">Открыть каталог</Link>
                  </Button>
                  <Button variant="outline" className="w-full rounded-2xl sm:w-auto" size="lg" asChild>
                    <Link href="/contacts">Консультация</Link>
                  </Button>
                  <Button variant="secondary" className="w-full rounded-2xl sm:w-auto" size="lg" asChild>
                    <a href={TELEGRAM_URL} target="_blank" rel="noopener noreferrer">
                      Telegram
                    </a>
                  </Button>
                </div>
              </div>

              <div className="relative mx-auto w-full max-w-xl lg:mx-0 lg:max-w-none">
                <div className="relative aspect-[4/3] overflow-hidden rounded-2xl bg-muted shadow-lg ring-1 ring-black/5 sm:aspect-[16/11] lg:aspect-[5/4]">
                  <Image
                    src={HERO_IMAGE}
                    alt="Подобранный автомобиль — иллюстрация раздела"
                    fill
                    priority
                    className="object-cover"
                    sizes="(max-width: 1024px) 100vw, 50vw"
                  />
                </div>
                <div
                  className="pointer-events-none absolute -inset-4 -z-10 rounded-[2rem] bg-gradient-to-br from-primary/5 via-transparent to-chart-2/10 blur-2xl"
                  aria-hidden
                />
              </div>
            </div>
          </section>
        </MotionFadeUp>

        {/* Быстрые преимущества */}
        <MotionFadeUp delay={0.06} className="mt-6 sm:mt-8">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:gap-4">
            <FeatureTile icon={Car} title="Выбрать авто в каталоге">
              <p>Фильтры по рынку, цене и характеристикам — Корея и Китай в одном интерфейсе.</p>
            </FeatureTile>
            <FeatureTile icon={Video} title="Видеоотчёты осмотра">
              <p className="mb-3">Фото и видео с площадки, чтобы принять решение дистанционно.</p>
              <a
                href={VIDEO_REPORTS_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
              >
                Примеры на Яндекс.Диске
                <ArrowRight className="h-3.5 w-3.5" aria-hidden />
              </a>
            </FeatureTile>
            <FeatureTile icon={Globe2} title="Доставка и логистика">
              <p>Ориентируемся на ваш маршрут и сроки; подскажем по этапам оформления.</p>
            </FeatureTile>
            <FeatureTile icon={Sparkles} title="Работаем с 2021 года">
              <p>Опыт подбора из Азии и сопровождения сделок — без лишних посредников.</p>
            </FeatureTile>
          </div>
        </MotionFadeUp>

        {/* Условия сотрудничества */}
        <MotionFadeUp delay={0.08} className="mt-14 sm:mt-20">
          <SectionHeading
            title="Комфортные условия сотрудничества"
            subtitle="Договор, контроль по пути и понятные опции хранения — всё фиксируем письменно."
          />
          <MotionStagger className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6">
            <MotionStaggerItem>
              <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm ring-1 ring-elevated-ring transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md">
                <div className="relative flex h-40 items-center justify-center bg-gradient-to-br from-muted to-muted/40">
                  <FileText className="h-14 w-14 text-primary/80" aria-hidden />
                </div>
                <div className="flex flex-1 flex-col p-5">
                  <h3 className="text-lg font-semibold text-foreground">Работаем по договору</h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                    Закрепляем условия оферты и реквизиты, описание автомобиля и обязанности сторон — без
                    «устных договорённостей».
                  </p>
                  <Link
                    href="/contacts"
                    className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline"
                  >
                    Запросить образец
                    <ArrowRight className="h-4 w-4" aria-hidden />
                  </Link>
                </div>
              </article>
            </MotionStaggerItem>
            <MotionStaggerItem>
              <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm ring-1 ring-elevated-ring transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md">
                <div className="relative flex h-40 items-center justify-center bg-gradient-to-br from-chart-2/15 to-muted">
                  <MapPin className="h-14 w-14 text-chart-2" aria-hidden />
                </div>
                <div className="flex flex-1 flex-col p-5">
                  <h3 className="text-lg font-semibold text-foreground">Контроль перемещения</h3>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                    По согласованию подключаем трекинг и статусы по ключевым точкам маршрута — меньше
                    неопределённости.
                  </p>
                </div>
              </article>
            </MotionStaggerItem>
            <MotionStaggerItem className="sm:col-span-2 lg:col-span-1">
              <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-border/60 bg-card shadow-sm ring-1 ring-elevated-ring transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md">
                <div className="relative flex h-40 items-center justify-center bg-gradient-to-br from-chart-1/15 to-muted">
                  <Warehouse className="h-14 w-14 text-chart-1" aria-hidden />
                </div>
                <div className="flex flex-1 flex-col p-5">
                  <h3 className="text-lg font-semibold text-foreground">Хранение в Южной Корее</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    Можно выкупить авто заранее и оставить на стоянке до выгодного окна по утильсбору или
                    ставке — отправим, когда будете готовы.
                  </p>
                </div>
              </article>
            </MotionStaggerItem>
          </MotionStagger>
        </MotionFadeUp>

        {/* Личный менеджер */}
        <MotionFadeUp delay={0.06} className="mt-10 sm:mt-12">
          <div className="flex flex-col gap-8 overflow-hidden rounded-2xl border border-border/60 bg-gradient-to-br from-muted/50 via-card to-card p-6 shadow-sm ring-1 ring-elevated-ring sm:flex-row sm:items-center sm:justify-between sm:p-8 lg:p-10">
            <div className="max-w-2xl min-w-0">
              <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/80 px-3 py-1 text-xs font-medium text-muted-foreground">
                <Headphones className="h-3.5 w-3.5 text-primary" aria-hidden />
                Сопровождение сделки
              </div>
              <h3 className="mt-4 text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
                Курируем автомобиль до вручения
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground sm:text-base">
                Личный менеджер на связи на всех этапах: от подбора и проверки до логистики и вопросов по
                документам.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Button asChild size="lg" className="rounded-2xl">
                  <Link href="/contacts">Связаться</Link>
                </Button>
                <Button variant="outline" asChild size="lg" className="rounded-2xl">
                  <Link href="/buy">Как купить</Link>
                </Button>
              </div>
            </div>
            <div className="relative mx-auto flex h-36 w-full max-w-xs shrink-0 items-center justify-center rounded-2xl bg-primary/10 sm:h-40 sm:w-48">
              <Headphones className="h-16 w-16 text-primary/90 sm:h-20 sm:w-20" aria-hidden />
            </div>
          </div>
        </MotionFadeUp>

        {/* Видеообзоры */}
        <MotionFadeUp delay={0.06} className="mt-14 sm:mt-20">
          <div className="border-t border-border/60 pt-12 sm:pt-16">
            <h3 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
              Подробные видеообзоры и отчёты
            </h3>
            <p className="mt-3 max-w-3xl text-pretty text-sm leading-relaxed text-muted-foreground sm:text-base">
              Осмотр выполняет специалист: кузов и салон, узлы и агрегаты, ходовая часть. Дефекты фиксируем на
              фото и видео — вы получаете материалы для решения о покупке до оплаты.
            </p>
            <div className="mt-8 grid gap-4 sm:grid-cols-3 sm:gap-5">
              <VideoThumbCard
                href={VIDEO_REPORTS_URL}
                label="Архив видеоотчётов"
                thumbSrc="https://images.unsplash.com/photo-1619405399517-d7fce0f13302?auto=format&fit=crop&w=800&q=80"
                thumbAlt="Интерьер автомобиля — превью видеоотчёта"
              />
              <VideoThumbCard
                href={VIDEO_REPORTS_URL}
                label="Примеры осмотра кузова"
                thumbSrc="https://images.unsplash.com/photo-1486262715619-067b786738f6?auto=format&fit=crop&w=800&q=80"
                thumbAlt="Кузов автомобиля — превью видеоотчёта"
              />
              <VideoThumbCard
                href="/contacts"
                label="Заказать осмотр вашего лота"
                thumbSrc="https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=800&q=80"
                thumbAlt="Автомобиль на дороге — заявка на осмотр"
              />
            </div>
          </div>
        </MotionFadeUp>

        <div className="mt-12 sm:mt-14">
          <HomeTrustStrip />
        </div>

        <p className="mt-10 text-center text-sm leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
          Полный каталог с фильтрами — в разделе{" "}
          <Link className="font-medium text-primary underline-offset-4 hover:underline" href="/catalog">
            Каталог
          </Link>
          . SEO-страницы по маркам Кореи — в{" "}
          <code className="break-all rounded-md bg-muted px-1.5 py-0.5 text-xs text-foreground">
            /seo/korea/…
          </code>
          .
        </p>
      </div>
    </div>
  );
}
