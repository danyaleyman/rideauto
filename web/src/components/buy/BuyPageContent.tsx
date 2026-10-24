"use client";

import { useLocaleContext } from "@/components/LocaleProvider";
import { BuyCalculatorLazy } from "@/components/buy/BuyCalculatorLazy";
import { OrderLeadForm } from "@/components/buy/OrderLeadForm";
import { MotionFadeUp } from "@/components/ui/motion";

export function BuyPageContent() {
  const { t } = useLocaleContext();
  const steps = [
    { id: "buy-step-1", text: t("buy.step1") },
    { id: "buy-step-2", text: t("buy.step2") },
    { id: "buy-step-3", text: t("buy.step3") },
    { id: "buy-step-4", text: t("buy.step4") },
  ] as const;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <MotionFadeUp>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("buy.h1")}</h1>
        <p className="mt-3 max-w-3xl text-muted-foreground">{t("buy.lead")}</p>
        <nav aria-label={t("buy.navAria")} className="mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm">
          <a href="#buy-steps" className="text-foreground underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">
            {t("buy.navSteps")}
          </a>
          <a href="#order-lead" className="text-foreground underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">
            {t("buy.navForm")}
          </a>
          <a href="#buy-calculator" className="text-foreground underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">
            {t("buy.navCalculator")}
          </a>
        </nav>
      </MotionFadeUp>

      <MotionFadeUp delay={0.04}>
        <section id="buy-steps" aria-labelledby="buy-steps-heading" className="mt-10 scroll-mt-24">
          <h2 id="buy-steps-heading" className="sr-only">
            {t("buy.stepsSr")}
          </h2>
          <ol className="grid list-none gap-x-10 gap-y-8 sm:grid-cols-2">
            {steps.map((step, i) => (
              <li key={step.id} id={step.id} className="border-t border-border pt-4">
                <p className="text-sm font-medium tabular-nums text-muted-foreground">{String(i + 1).padStart(2, "0")}</p>
                <p className="mt-2 text-sm leading-6 text-foreground">{step.text}</p>
              </li>
            ))}
          </ol>
        </section>
      </MotionFadeUp>

      <MotionFadeUp delay={0.08}>
        <OrderLeadForm />
      </MotionFadeUp>

      <MotionFadeUp delay={0.12}>
        <div id="buy-calculator" className="mt-10 scroll-mt-24">
          <h2 className="text-lg font-semibold tracking-tight text-foreground">{t("buy.calcTitle")}</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{t("buy.calcHint")}</p>
          <div className="mt-6">
            <BuyCalculatorLazy />
          </div>
        </div>
      </MotionFadeUp>
    </div>
  );
}
