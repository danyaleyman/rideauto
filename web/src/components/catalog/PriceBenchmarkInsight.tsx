"use client";

import { Info } from "lucide-react";
import {
  formatPriceRangeShort,
  type PriceBenchmarkResponse,
} from "@/lib/catalog-price-benchmark";
import { formatPriceLabel } from "@/lib/format-price";
import { useLocaleContext } from "@/components/LocaleProvider";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  data: PriceBenchmarkResponse | undefined;
  loading?: boolean;
  variant: "catalog" | "car";
  className?: string;
};

function bandStyles(band: string | undefined): { dot: string; text: string } {
  if (band === "below_typical") {
    return {
      dot: "bg-amber-500",
      text: "text-amber-700 dark:text-amber-300",
    };
  }
  if (band === "above_typical") {
    return {
      dot: "bg-red-500",
      text: "text-red-700 dark:text-red-400",
    };
  }
  if (band === "typical") {
    return {
      dot: "bg-emerald-500",
      text: "text-emerald-700 dark:text-emerald-400",
    };
  }
  return { dot: "bg-muted-foreground/40", text: "text-muted-foreground" };
}

export function PriceBenchmarkInsight({ data, loading, variant, className }: Props) {
  const { t } = useLocaleContext();
  const peer = data?.peer_all;
  if (loading) {
    return (
      <p className={cn("text-xs text-muted-foreground", className)} aria-hidden>
        {t("catalog.benchmark.loading")}
      </p>
    );
  }
  if (!data?.eligible || !peer?.median_rub || peer.p25_rub == null || peer.p75_rub == null) {
    return null;
  }

  const range = formatPriceRangeShort(peer.p25_rub, peer.p75_rub);
  const median = formatPriceLabel(peer.median_rub);
  const market = data.cohort.market ?? "korea";
  const peerClean = data.peer_clean;
  const listing = data.listing;

  const bandLabel =
    listing?.band === "below_typical"
      ? t("catalog.benchmark.belowTypical")
      : listing?.band === "above_typical"
        ? t("catalog.benchmark.aboveTypical")
        : listing?.band === "typical"
          ? t("catalog.benchmark.withinTypical")
          : null;

  const vsPct =
    listing?.vs_median_all_pct != null && listing.vs_median_all_pct !== 0
      ? listing.vs_median_all_pct < 0
        ? t("catalog.benchmark.vsMedianBelow", { pct: Math.abs(listing.vs_median_all_pct) })
        : t("catalog.benchmark.vsMedianAbove", { pct: listing.vs_median_all_pct })
      : null;

  const styles = bandStyles(listing?.band);

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-muted/40 px-3.5 py-3 text-xs leading-snug",
        variant === "car" && "mt-4",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-foreground">{t("catalog.benchmark.title")}</p>
        <Dialog>
          <DialogTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className="size-7 shrink-0 rounded-lg"
              aria-label={t("catalog.benchmark.howAria")}
            >
              <Info className="size-3.5" aria-hidden />
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{t("catalog.benchmark.howTitle")}</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">{t("catalog.benchmark.howBody")}</p>
            {market === "china" ? (
              <p className="text-sm text-muted-foreground">{t("catalog.benchmark.disclaimerChina")}</p>
            ) : (
              <p className="text-sm text-muted-foreground">{t("catalog.benchmark.disclaimerKorea")}</p>
            )}
          </DialogContent>
        </Dialog>
      </div>
      <p className="mt-1 text-muted-foreground">
        {t("catalog.benchmark.typicalLine", { range, median, n: peer.n })}
      </p>
      {market === "korea" && peerClean?.median_rub && peerClean.p25_rub != null && peerClean.p75_rub != null ? (
        <p className="mt-1 text-muted-foreground">
          {t("catalog.benchmark.cleanLine", {
            range: formatPriceRangeShort(peerClean.p25_rub, peerClean.p75_rub),
            n: peerClean.n,
          })}
        </p>
      ) : market === "china" ? (
        <p className="mt-1 text-muted-foreground/90">{t("catalog.benchmark.disclaimerChinaShort")}</p>
      ) : null}
      {variant === "car" && listing && bandLabel ? (
        <div className="mt-2.5 flex items-center gap-2">
          <span className={cn("size-2 shrink-0 rounded-full", styles.dot)} aria-hidden />
          <p className={cn("font-medium", styles.text)}>
            {bandLabel}
            {vsPct && (listing.band === "below_typical" || listing.band === "above_typical")
              ? ` · ${vsPct}`
              : null}
          </p>
        </div>
      ) : null}
      {variant === "car" && listing?.band === "below_typical" ? (
        <p className="mt-1 text-muted-foreground">{t("catalog.benchmark.belowHint")}</p>
      ) : null}
    </div>
  );
}
