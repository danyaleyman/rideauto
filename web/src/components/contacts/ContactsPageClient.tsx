"use client";

import { MotionFadeUp } from "@/components/ui/motion";
import { Button } from "@/components/ui/button";
import { useLocaleContext } from "@/components/LocaleProvider";

export function ContactsPageClient() {
  const { t } = useLocaleContext();

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <MotionFadeUp>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("contacts.title")}</h1>
        <p className="mt-3 max-w-2xl text-muted-foreground">{t("contacts.lead")}</p>
      </MotionFadeUp>

      <MotionFadeUp delay={0.04}>
        <dl className="mt-10 divide-y divide-border border-t border-border">
          <div className="grid grid-cols-1 gap-1 py-4 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-6">
            <dt className="text-sm text-muted-foreground">{t("contacts.telegram")}</dt>
            <dd className="min-w-0 text-sm leading-6 text-foreground">
              <span className="text-muted-foreground">{t("contacts.manager")}: </span>
              <a
                className="underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground"
                href="https://t.me/nikits15"
                target="_blank"
                rel="noopener noreferrer"
              >
                @nikits15
              </a>
              <span className="text-muted-foreground"> · {t("contacts.channel")}: </span>
              <a
                className="underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground"
                href="https://t.me/worldrideauto"
                target="_blank"
                rel="noopener noreferrer"
              >
                @worldrideauto
              </a>
            </dd>
          </div>
          <div className="grid grid-cols-1 gap-1 py-4 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-6">
            <dt className="text-sm text-muted-foreground">{t("contacts.vk")}</dt>
            <dd className="min-w-0 text-sm leading-6">
              <a
                className="underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground"
                href="https://vk.com/ride_auto"
                target="_blank"
                rel="noopener noreferrer"
              >
                vk.com/ride_auto
              </a>
            </dd>
          </div>
          <div className="grid grid-cols-1 gap-1 py-4 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-6">
            <dt className="text-sm text-muted-foreground">{t("contacts.avito")}</dt>
            <dd className="min-w-0 text-sm leading-6">
              <a
                className="underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground"
                href="https://www.avito.ru/brands/8a805bbde7bfbfcc9b9e810b88bb4382?src=sharing"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("contacts.companyProfile")}
              </a>
            </dd>
          </div>
        </dl>
      </MotionFadeUp>

      <MotionFadeUp delay={0.08}>
        <div className="mt-8">
          <Button asChild className="h-11 px-5">
            <a href="https://t.me/nikits15" target="_blank" rel="noopener noreferrer">
              {t("contacts.writeCta")}
            </a>
          </Button>
        </div>
      </MotionFadeUp>
    </div>
  );
}
