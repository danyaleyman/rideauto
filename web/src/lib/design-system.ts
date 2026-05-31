import { cn } from "@/lib/utils";

/** Единая высота интерактивных контролов на money-pages (каталог, карточка, buy). */
export const controlHeightClass = "h-10";

/** Радиус полей, кнопок, dropdown-триггеров. */
export const controlRadiusClass = "rounded-2xl";

/** Радиус панелей и карточек-контейнеров. */
export const surfaceRadiusClass = "rounded-3xl";

/** Пилюли: чипы, market tabs, pagination. */
export const pillRadiusClass = "rounded-full";

/** Минимум 44×44px на coarse pointer (iOS / Android). */
export const touchTargetClass =
  "max-lg:min-h-11 max-lg:min-w-11 lg:min-h-0 lg:min-w-0";

export const touchIconButtonClass = "size-11 sm:size-8";

/** Семантическая обводка elevated-поверхностей (см. --elevated-ring в globals.css). */
export const elevatedRingClass = "ring-1 ring-elevated-ring";

export const elevatedSurfaceClass = cn("shadow-sm", elevatedRingClass);

export const elevatedSurfaceHoverClass = cn(
  "transition-[transform,box-shadow] duration-300 ease-out will-change-transform",
  "hover:-translate-y-px hover:shadow-md",
  "motion-reduce:transform-none motion-reduce:transition-none motion-reduce:hover:translate-y-0",
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
  "rounded-t-2xl md:rounded-s-2xl md:rounded-tr-none",
);

export const siteHeaderSafeTopClass = "pt-[env(safe-area-inset-top)]";
