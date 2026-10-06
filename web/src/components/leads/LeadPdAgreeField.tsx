"use client";

import Link from "next/link";
import { Checkbox } from "@/components/ui/checkbox";
import { useLocaleContext } from "@/components/LocaleProvider";

type Props = {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  /** catalog.quickBuy.pdPrefix vs buy.pdAgree */
  variant?: "quickBuy" | "buy";
  className?: string;
};

/** Shared PD consent block for lead forms (QuickBuy + /buy). */
export function LeadPdAgreeField({
  checked,
  onCheckedChange,
  variant = "quickBuy",
  className,
}: Props) {
  const { t } = useLocaleContext();
  const prefix = variant === "buy" ? t("buy.pdAgree") : t("catalog.quickBuy.pdPrefix");
  const aria = variant === "buy" ? t("buy.pdAgree") : t("catalog.quickBuy.pdAria");

  return (
    <div className={className ?? "rounded-xl border border-border/70 bg-muted/25 p-3 sm:p-4"}>
      <label className="flex items-start gap-3 text-xs text-foreground/90 sm:text-sm">
        <Checkbox
          checked={checked}
          onCheckedChange={(v) => onCheckedChange(v === true)}
          className="mt-0.5 border-foreground/25"
          aria-label={aria}
        />
        <span className="leading-snug">
          {prefix}{" "}
          <Link
            href="/privacy"
            className="font-medium text-primary underline underline-offset-4 hover:text-primary/90"
          >
            {t("buy.privacyLink")}
          </Link>
          .
        </span>
      </label>
    </div>
  );
}
