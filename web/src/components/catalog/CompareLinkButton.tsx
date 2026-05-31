"use client";



import Link from "next/link";

import { GitCompareArrows } from "lucide-react";

import { Button } from "@/components/ui/button";

import { useCompareCars } from "@/hooks/use-compare-cars";

import { useLocaleContext } from "@/components/LocaleProvider";



/** Ссылка на страницу сравнения с бейджем количества. */

export function CompareLinkButton({ className }: { className?: string }) {

  const { compareHref, count } = useCompareCars();

  const { t } = useLocaleContext();



  return (

    <Button variant="ghost" size="sm" asChild className={className}>

      <Link href={compareHref} aria-label={t("compare.navLabel", { count: String(count) })}>

        <GitCompareArrows className="size-4 shrink-0" aria-hidden />

        <span className="hidden sm:inline">{t("compare.nav")}</span>

        {count > 0 ? (

          <span className="ms-1 inline-flex min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground">

            {count}

          </span>

        ) : null}

      </Link>

    </Button>

  );

}


