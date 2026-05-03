import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { featureFlags } from "@/lib/feature-flags";
import { t } from "@/lib/i18n";

const items = [
  { titleKey: "home.trust.item1Title", bodyKey: "home.trust.item1Body" },
  { titleKey: "home.trust.item2Title", bodyKey: "home.trust.item2Body" },
  { titleKey: "home.trust.item3Title", bodyKey: "home.trust.item3Body" },
] as const;

export function HomeTrustStrip() {
  if (!featureFlags.showHomeTrustStrip) return null;

  return (
    <section
      className="mt-10 rounded-2xl border border-border/60 bg-card/70 p-5 shadow-sm ring-1 ring-elevated-ring backdrop-blur-sm sm:mt-12 sm:p-6"
      aria-labelledby="home-trust-heading"
    >
      <h2 id="home-trust-heading" className="sr-only">
        {t("home.trust.srHeading")}
      </h2>
      <ul className="grid gap-4 sm:grid-cols-3 sm:gap-5">
        {items.map((item) => (
          <li key={item.titleKey} className="flex gap-3 rounded-xl bg-muted/20 p-3 sm:p-4">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary">
              <CheckCircle2 className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="font-medium leading-snug text-foreground">{t(item.titleKey)}</p>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t(item.bodyKey)}</p>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-5 flex flex-wrap gap-3 text-sm font-medium">
        <Link className="text-primary underline-offset-4 hover:underline" href="/contacts">
          {t("home.trust.contactsLink")}
        </Link>
        <Link className="text-primary underline-offset-4 hover:underline" href="/buy">
          {t("home.trust.howToBuyLink")}
        </Link>
      </div>
    </section>
  );
}
