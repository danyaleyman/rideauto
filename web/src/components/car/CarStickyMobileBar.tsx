"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { MessageCircle } from "lucide-react";
import type { CarListingAvailability } from "@/lib/car-listing-trust";
import { useBottomChromeOffset } from "@/hooks/use-bottom-chrome-offset";
import { CatalogQuickBuyDialog } from "@/components/catalog/CatalogQuickBuyDialog";
import { MOTION_PRESETS, MOTION_TOKENS } from "@/components/ui/motion";
import { useLocaleContext } from "@/components/LocaleProvider";
import { cn } from "@/lib/utils";

type Props = {
  carId: string;
  carTitle: string;
  priceLine: string;
  availability?: CarListingAvailability;
};

/** Фиксированная панель цены + CTA на телефоне (как у агрегаторов). */
export function CarStickyMobileBar({
  carId,
  carTitle,
  priceLine,
  availability = "available",
}: Props) {
  const { t } = useLocaleContext();
  const reduceMotion = useReducedMotion();
  const cookieOffset = useBottomChromeOffset();

  const caption =
    availability === "sold" || availability === "reserved"
      ? t("car.purchase.statusHeading")
      : t("car.purchase.priceHeading");

  const isAvailable = availability === "available";
  const stickyCtaClass =
    "flex h-11 min-w-[7.5rem] shrink-0 items-center justify-center rounded-lg px-5 text-center text-sm font-semibold transition-colors";
  const stickyBuyClass = cn(stickyCtaClass, "bg-primary text-primary-foreground hover:bg-primary/85");
  // При доступном авто «Связаться» — компактная иконка рядом с главной CTA; иначе — единственная кнопка.
  const stickyContactClass = cn(
    stickyCtaClass,
    "border border-input bg-background text-foreground hover:bg-muted",
    isAvailable && "w-11 min-w-0 px-0",
  );

  return (
    <motion.div
      className={cn(
        "fixed inset-x-0 z-40 lg:hidden",
        "border-t border-border bg-background/95 backdrop-blur-xl",
        "pb-[max(0.65rem,env(safe-area-inset-bottom))]",
      )}
      style={{ bottom: cookieOffset }}
      initial={reduceMotion ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={reduceMotion ? { duration: 0.01 } : { duration: 0.24, ease: MOTION_TOKENS.easeSoft }}
    >
      <div className="mx-auto flex max-w-lg items-center justify-between gap-3 px-4 pt-2.5">
        <div className="min-w-0 flex-1">
          <p className="sr-only">{caption}</p>
          <p
            className={cn(
              "truncate text-base font-semibold leading-tight tracking-tight tabular-nums min-[420px]:text-lg",
              availability === "sold"
                ? "text-red-700 dark:text-red-300"
                : availability === "reserved"
                  ? "text-amber-800 dark:text-amber-200"
                  : "text-foreground",
            )}
          >
            {priceLine}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <motion.div {...(reduceMotion ? {} : MOTION_PRESETS.pressable)}>
            <Link
              href="/contacts"
              className={stickyContactClass}
              aria-label={isAvailable ? t("car.purchase.contactManager") : undefined}
              title={isAvailable ? t("car.purchase.contactManager") : undefined}
            >
              {isAvailable ? <MessageCircle className="size-5" aria-hidden /> : t("contacts.manager")}
            </Link>
          </motion.div>
          {isAvailable ? (
            <motion.div {...(reduceMotion ? {} : MOTION_PRESETS.pressable)}>
              <CatalogQuickBuyDialog
                carId={carId}
                carTitle={carTitle}
                triggerLabel={t("catalog.quickBuy.trigger")}
                triggerSize="default"
                triggerVariant="default"
                triggerClassName={stickyBuyClass}
              />
            </motion.div>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}
