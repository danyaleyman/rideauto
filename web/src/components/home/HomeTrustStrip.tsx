"use client";

import Link from "next/link";
import { FileText, MessagesSquare, ShieldCheck, type LucideIcon } from "lucide-react";
import { useLocaleContext } from "@/components/LocaleProvider";
import { featureFlags } from "@/lib/feature-flags";

type TrustItem = { icon: LucideIcon; titleKey: string; bodyKey: string };

const itemKeys: TrustItem[] = [
  { icon: ShieldCheck, titleKey: "home.trust.item1Title", bodyKey: "home.trust.item1Body" },
  { icon: FileText, titleKey: "home.trust.item2Title", bodyKey: "home.trust.item2Body" },
  { icon: MessagesSquare, titleKey: "home.trust.item3Title", bodyKey: "home.trust.item3Body" },
];

/** Короткий блок доверия (проверка, логистика, на связи) — вынесен в клиентский вид под главную. */
export function HomeTrustStrip() {
  const { t } = useLocaleContext();

  if (!featureFlags.showHomeTrustStrip) return null;

  return (
    <section aria-labelledby="home-trust-heading" className="border-t border-border bg-muted/40">
      <div className="mx-auto max-w-[1440px] px-4 py-12 sm:px-6 sm:py-16 lg:px-10">
        <h2 id="home-trust-heading" className="sr-only">
          {t("home.trust.srHeading")}
        </h2>
        <ul className="grid gap-x-10 gap-y-8 sm:grid-cols-3">
          {itemKeys.map(({ icon: Icon, titleKey, bodyKey }) => (
            <li key={titleKey} className="flex min-w-0 gap-4">
              <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground">
                <Icon className="size-4" aria-hidden />
              </span>
              <div className="min-w-0">
                <p className="font-medium leading-snug text-foreground">{t(titleKey)}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{t(bodyKey)}</p>
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-border/70 pt-6 text-sm font-medium">
          <Link className="text-foreground underline-offset-4 hover:underline" href="/contacts">
            {t("home.trust.contactsLink")}
          </Link>
          <Link className="text-foreground underline-offset-4 hover:underline" href="/buy">
            {t("home.trust.howToBuyLink")}
          </Link>
        </div>
      </div>
    </section>
  );
}
