"use client";

import { MotionFadeUp, MotionStagger, MotionStaggerItem } from "@/components/ui/motion";
import { useLocaleContext } from "@/components/LocaleProvider";

export function ContactsPageClient() {
  const { t } = useLocaleContext();

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <MotionFadeUp>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("contacts.title")}</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">{t("contacts.lead")}</p>
      </MotionFadeUp>

      <MotionStagger className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <MotionStaggerItem>
          <article className="rounded-2xl border border-border/70 bg-card p-5 shadow-sm">
            <h2 className="text-lg font-semibold">{t("contacts.telegram")}</h2>
            <p className="mt-2 text-sm">
              {t("contacts.manager")}:{" "}
              <a className="text-primary underline-offset-2 hover:underline" href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
                @nikits15
              </a>
            </p>
            <p className="mt-1 text-sm">
              {t("contacts.channel")}:{" "}
              <a className="text-primary underline-offset-2 hover:underline" href="https://t.me/worldrideauto" target="_blank" rel="noopener noreferrer">
                @worldrideauto
              </a>
            </p>
          </article>
        </MotionStaggerItem>
        <MotionStaggerItem>
          <article className="rounded-2xl border border-border/70 bg-card p-5 shadow-sm">
            <h2 className="text-lg font-semibold">{t("contacts.vk")}</h2>
            <p className="mt-2 text-sm">
              <a className="text-primary underline-offset-2 hover:underline" href="https://vk.com/ride_auto" target="_blank" rel="noopener noreferrer">
                vk.com/ride_auto
              </a>
            </p>
          </article>
        </MotionStaggerItem>
        <MotionStaggerItem>
          <article className="rounded-2xl border border-border/70 bg-card p-5 shadow-sm">
            <h2 className="text-lg font-semibold">{t("contacts.avito")}</h2>
            <p className="mt-2 text-sm">
              <a
                className="text-primary underline-offset-2 hover:underline"
                href="https://www.avito.ru/brands/8a805bbde7bfbfcc9b9e810b88bb4382?src=sharing"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("contacts.companyProfile")}
              </a>
            </p>
          </article>
        </MotionStaggerItem>
      </MotionStagger>
    </div>
  );
}
