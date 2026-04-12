import type { Metadata } from "next";
import { BuyCalculator } from "@/components/buy/BuyCalculator";
import { OrderLeadForm } from "@/components/buy/OrderLeadForm";

export const metadata: Metadata = {
  title: "Как купить",
  description:
    "Этапы покупки автомобиля из Кореи и Китая, ориентировочный калькулятор и форма заявки — World Ride Auto.",
  alternates: { canonical: "/buy" },
};

export default function BuyPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-semibold tracking-tight text-foreground">Как купить автомобиль</h1>
      <p className="mt-3 max-w-3xl text-muted-foreground">
        Согласуем бюджет и профиль, подберём варианты на площадках Кореи и Китая, организуем выкуп, доставку и
        таможенное оформление.
      </p>

      <ol className="mt-8 grid gap-3 rounded-2xl border border-border/60 bg-card/70 p-6 text-sm text-foreground sm:grid-cols-2">
        <li>1. Консультация и целевой профиль автомобиля.</li>
        <li>2. Проверка состояния и финальный выбор.</li>
        <li>3. Выкуп и доставка до порта.</li>
        <li>4. Таможня и передача автомобиля.</li>
      </ol>

      <OrderLeadForm />

      <div className="mt-10">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">Ориентировочный расчёт</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Упрощённая модель расходов; итог по сделке зависит от курса, лота и условий перевозчика.
        </p>
        <div className="mt-6">
          <BuyCalculator />
        </div>
      </div>
    </div>
  );
}
