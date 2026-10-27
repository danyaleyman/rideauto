"use client";

import { Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, GitCompareArrows, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchCompareClient, type CompareCarRow } from "@/lib/client-api";
import { formatCatalogCardPriceLocale } from "@/lib/format-price-locale";
import type { AppLocale } from "@/lib/i18n";
import { useCompareCars } from "@/hooks/use-compare-cars";
import { useLocaleContext } from "@/components/LocaleProvider";

function CompareTable({ rows, locale }: { rows: CompareCarRow[]; locale: AppLocale }) {
  const { t } = useLocaleContext();
  const fields: Array<{ key: keyof CompareCarRow; labelKey: string }> = [
    { key: "price_rub", labelKey: "compare.price" },
    { key: "year", labelKey: "compare.year" },
    { key: "mileage_km", labelKey: "compare.mileage" },
    { key: "fuel", labelKey: "compare.fuel" },
    { key: "transmission", labelKey: "compare.transmission" },
    { key: "power_hp", labelKey: "compare.power" },
    { key: "body_type", labelKey: "compare.body" },
    { key: "drive_type", labelKey: "compare.drive" },
  ];

  const formatCell = (key: keyof CompareCarRow, row: CompareCarRow) => {
    const v = row[key];
    if (key === "price_rub")
      return formatCatalogCardPriceLocale(locale, v as number | null | undefined);
    if (v == null || v === "") return "—";
    return String(v);
  };

  return (
    <div className="overflow-x-auto rounded-xl border border-border/70">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/60 bg-muted/30">
            <th scope="col" className="px-3 py-2 text-left font-medium text-muted-foreground">
              {t("compare.paramLabel")}
            </th>
            {rows.map((row) => (
              <th key={row.id} scope="col" className="min-w-[10rem] px-3 py-2 text-left align-top">
                <Link href={row.url_path} className="font-semibold text-primary hover:underline">
                  {row.title}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b border-border/50">
            <th scope="row" className="px-3 py-2 text-left font-medium text-muted-foreground">
              {t("compare.photo")}
            </th>
            {rows.map((row) => (
              <td key={row.id} className="px-3 py-2 align-top">
                {row.thumb_url ? (
                  <Image
                    src={row.thumb_url}
                    alt=""
                    width={120}
                    height={80}
                    className="h-20 w-auto rounded-lg object-cover"
                    unoptimized
                  />
                ) : (
                  "—"
                )}
              </td>
            ))}
          </tr>
          {fields.map(({ key, labelKey }) => (
            <tr key={key} className="border-b border-border/40">
              <th scope="row" className="px-3 py-2 text-left font-medium text-muted-foreground">
                {t(labelKey)}
              </th>
              {rows.map((row) => (
                <td key={row.id} className="px-3 py-2 align-top">
                  {formatCell(key, row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ComparePageInner() {
  const { t, locale } = useLocaleContext();
  const searchParams = useSearchParams();
  const { ids: storedIds, remove, clear, compareHref } = useCompareCars();
  const urlIds = (searchParams.get("ids") || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
  const ids = urlIds.length ? urlIds : storedIds;

  const query = useQuery({
    queryKey: ["compare", ids.join(",")],
    queryFn: ({ signal }) => fetchCompareClient(ids, { signal }),
    enabled: ids.length > 0,
  });

  const rows = query.data?.result ?? [];

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" asChild className="rounded-full gap-1.5">
          <Link href="/catalog">
            <ArrowLeft className="size-4" aria-hidden />
            {t("compare.backToCatalog")}
          </Link>
        </Button>
        {ids.length ? (
          <Button variant="outline" size="sm" className="rounded-full gap-1.5" onClick={() => clear()}>
            <Trash2 className="size-4" aria-hidden />
            {t("compare.clear")}
          </Button>
        ) : null}
      </div>

      <h1 className="mb-2 flex items-center gap-2 text-2xl font-semibold tracking-tight">
        <GitCompareArrows className="size-7 shrink-0 text-primary" aria-hidden />
        {t("compare.title")}
      </h1>
      <p className="mb-8 max-w-2xl text-sm text-muted-foreground">{t("compare.hint")}</p>

      {!ids.length ? (
        <p className="rounded-xl border border-dashed border-border/70 bg-muted/20 px-4 py-8 text-center text-sm text-muted-foreground">
          {t("compare.empty")}{" "}
          <Link href="/catalog" className="text-primary underline-offset-2 hover:underline">
            {t("compare.openCatalog")}
          </Link>
        </p>
      ) : query.isLoading ? (
        <p className="text-sm text-muted-foreground">{t("compare.loading")}</p>
      ) : query.isError ? (
        <p className="text-sm text-destructive">{t("compare.error")}</p>
      ) : (
        <>
          <CompareTable rows={rows} locale={locale} />
          <ul className="mt-4 flex flex-wrap gap-2" aria-label={t("compare.listLabel")}>
            {ids.map((id) => (
              <li key={id}>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="rounded-full text-xs"
                  onClick={() => remove(id)}
                >
                  {t("compare.remove")}: {id.slice(0, 12)}…
                </Button>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-xs text-muted-foreground">
            <Link href={compareHref} className="underline-offset-2 hover:underline">
              {t("compare.shareLink")}
            </Link>
          </p>
        </>
      )}
    </main>
  );
}

export default function ComparePage() {
  const { t } = useLocaleContext();
  return (
    <Suspense fallback={<main className="px-4 py-12 text-sm text-muted-foreground">{t("compare.loading")}</main>}>
      <ComparePageInner />
    </Suspense>
  );
}
