import { cn } from "@/lib/utils";

/** Единая высота интерактивных контролов на money-pages (каталог, карточка, buy). */
export const controlHeightClass = "h-10";

/** Радиус полей, кнопок, dropdown-триггеров. */
export const controlRadiusClass = "rounded-lg";

/** Радиус панелей и карточек-контейнеров. */
export const surfaceRadiusClass = "rounded-xl";

/** Пилюли: чипы, market tabs, pagination. */
export const pillRadiusClass = "rounded-full";

/** Минимум 44×44px на coarse pointer (iOS / Android). */
export const touchTargetClass =
  "max-lg:min-h-11 max-lg:min-w-11 lg:min-h-0 lg:min-w-0";

export const touchIconButtonClass = "size-11 sm:size-8";

/**
 * Обводка «приподнятых» поверхностей. Одна тонкая граница — без shadow+ring
 * одновременно (тройная обводка читается как визуальный шум).
 */
export const elevatedRingClass = "border border-border";

export const elevatedSurfaceClass = cn("bg-card", elevatedRingClass, surfaceRadiusClass);

export const elevatedSurfaceHoverClass = cn(
  "transition-[border-color,box-shadow] duration-200 ease-out",
  "hover:border-foreground/20 hover:shadow-[0_6px_24px_-12px_rgba(15,23,42,0.25)]",
  "motion-reduce:transition-none",
);

export const listingCardSurfaceClass = cn(
  elevatedSurfaceClass,
  elevatedSurfaceHoverClass,
);

/** Превью в листинге: 4:3; ряд с md (не sm) — комфорт на планшетах 640–768px. */
export const catalogListingThumbClass =
  "relative w-full shrink-0 overflow-hidden aspect-[4/3] bg-muted/30 md:w-72";

export const catalogListingThumbFocusClass = cn(
  catalogListingThumbClass,
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
  "rounded-t-xl md:rounded-s-xl md:rounded-tr-none",
);

export const siteHeaderSafeTopClass = "pt-[env(safe-area-inset-top)]";
