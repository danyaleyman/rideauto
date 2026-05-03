import type { Metadata } from "next";
import { MessageCircle, ClipboardCheck, Ship, Landmark } from "lucide-react";
import { BuyCalculatorLazy } from "@/components/buy/BuyCalculatorLazy";
import { OrderLeadForm } from "@/components/buy/OrderLeadForm";
import { MotionFadeUp } from "@/components/ui/motion";

export const metadata: Metadata = {
  title: "Как купить",
  description:
    "Этапы покупки автомобиля из Кореи и Китая, ориентировочный калькулятор и форма заявки — World Ride Auto.",
  alternates: { canonical: "/buy" },
};

export default function BuyPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <MotionFadeUp>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Как купить автомобиль</h1>
        <p className="mt-3 max-w-3xl text-muted-foreground">
          Согласуем бюджет и профиль, подберём варианты на площадках Кореи и Китая, организуем выкуп, доставку и
          таможенное оформление.
        </p>
        <nav
          aria-label="Разделы страницы"
          className="mt-6 flex max-w-2xl flex-wrap gap-2 text-sm font-medium"
        >
          <a
            href="#buy-steps"
            className="rounded-full border border-border/70 bg-card/80 px-3 py-1.5 text-foreground shadow-sm transition-colors hover:border-primary/35 hover:bg-primary/5"
          >
            Этапы
          </a>
          <a
            href="#order-lead"
            className="rounded-full border border-border/70 bg-card/80 px-3 py-1.5 text-foreground shadow-sm transition-colors hover:border-primary/35 hover:bg-primary/5"
          >
            Заявка
          </a>
          <a
            href="#buy-calculator"
            className="rounded-full border border-border/70 bg-card/80 px-3 py-1.5 text-foreground shadow-sm transition-colors hover:border-primary/35 hover:bg-primary/5"
          >
            Калькулятор
          </a>
        </nav>
      </MotionFadeUp>

      <MotionFadeUp delay={0.04}>
        <section id="buy-steps" aria-labelledby="buy-steps-heading" className="mt-8 scroll-mt-24">
          <h2 id="buy-steps-heading" className="sr-only">
            Этапы покупки
          </h2>
          <ol className="grid list-none gap-3 rounded-2xl border border-border/60 bg-card/70 p-4 text-sm text-foreground sm:grid-cols-2 sm:p-6">
            <li id="buy-step-1" className="flex gap-3 rounded-xl bg-background/40 p-3 sm:p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary">
                <MessageCircle className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-medium leading-snug">1. Консультация и целевой профиль автомобиля.</p>
              </div>
            </li>
            <li id="buy-step-2" className="flex gap-3 rounded-xl bg-background/40 p-3 sm:p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary">
                <ClipboardCheck className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-medium leading-snug">2. Проверка состояния и финальный выбор.</p>
              </div>
            </li>
            <li id="buy-step-3" className="flex gap-3 rounded-xl bg-background/40 p-3 sm:p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary">
                <Ship className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-medium leading-snug">3. Выкуп и доставка до порта.</p>
              </div>
            </li>
            <li id="buy-step-4" className="flex gap-3 rounded-xl bg-background/40 p-3 sm:p-4">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/12 text-primary">
                <Landmark className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-medium leading-snug">4. Таможня и передача автомобиля.</p>
              </div>
            </li>
          </ol>
        </section>
      </MotionFadeUp>

      <MotionFadeUp delay={0.08}>
        <OrderLeadForm />
      </MotionFadeUp>

      <MotionFadeUp delay={0.12}>
        <div id="buy-calculator" className="mt-10 scroll-mt-24">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">Ориентировочный расчёт</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Упрощённая модель расходов; итог по сделке зависит от курса, лота и условий перевозчика.
          </p>
          <div className="mt-6">
            <BuyCalculatorLazy />
          </div>
        </div>
      </MotionFadeUp>
    </div>
  );
}
