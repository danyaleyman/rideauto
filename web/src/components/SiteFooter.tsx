"use client";

import Link from "next/link";
import { useLocaleContext } from "@/components/LocaleProvider";

export function SiteFooter() {
  const { t } = useLocaleContext();
  return (
    <footer className="border-t border-border/60 bg-muted/20">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-6 px-4 py-10 sm:px-6 lg:px-10">
        <nav className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
          <Link href="/catalog" className="hover:text-foreground">
            {t("footer.catalog")}
          </Link>
          <Link href="/buy" className="hover:text-foreground">
            {t("footer.buy")}
          </Link>
          <Link href="/contacts" className="hover:text-foreground">
            {t("footer.contacts")}
          </Link>
          <Link href="/privacy" className="hover:text-foreground">
            {t("footer.privacy")}
          </Link>
          <Link href="/agreement" className="hover:text-foreground">
            {t("footer.agreement")}
          </Link>
          <Link href="/cookies" className="hover:text-foreground">
            {t("footer.cookies")}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
