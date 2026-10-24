"use client";

import { cn } from "@/lib/utils";
import { controlHeightClass, pillRadiusClass } from "@/lib/design-system";

export const segmentedControlBarClass =
  "inline-flex w-full rounded-lg bg-muted p-1";

export const segmentedControlButtonClass =
  "flex-1 rounded-md px-3.5 py-2 text-sm font-medium leading-none transition";

export type SegmentedControlItem<T extends string> = {
  value: T;
  label: string;
};

type SegmentedControlBase<T extends string> = {
  value: T;
  onChange: (value: T) => void;
  items: readonly SegmentedControlItem<T>[];
  className?: string;
  "aria-label"?: string;
};

/** Горизонтальные табы с длинными подписями (комплектация и т.п.) — без сжатия в столбик. */
export function SegmentedControlScroll<T extends string>({
  value,
  onChange,
  items,
  className,
  "aria-label": ariaLabel,
}: SegmentedControlBase<T>) {
  return (
    <div
      className={cn(
        "flex gap-1 overflow-x-auto overscroll-x-contain rounded-lg bg-muted p-1 [-webkit-overflow-scrolling:touch]",
        className,
      )}
      role="tablist"
      aria-label={ariaLabel}
    >
      {items.map((item) => {
        const selected = value === item.value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={cn(
              "shrink-0 whitespace-nowrap rounded-md px-3.5 py-2 text-sm font-medium leading-snug transition",
              selected
                ? "bg-background text-foreground shadow-sm"
                : "text-foreground/70 hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/** Табы в аккордеонах и формах (rounded-2xl bar). */
export function SegmentedControl<T extends string>({
  value,
  onChange,
  items,
  className,
  "aria-label": ariaLabel,
}: SegmentedControlBase<T>) {
  return (
    <div
      className={cn(segmentedControlBarClass, className)}
      role="tablist"
      aria-label={ariaLabel}
    >
      {items.map((item) => {
        const selected = value === item.value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={cn(
              segmentedControlButtonClass,
              selected
                ? "bg-background text-foreground shadow-sm"
                : "text-foreground/70 hover:text-foreground",
            )}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/** Пилюля с ползунком (рынок Корея/Китай и аналогичные переключатели). */
export function SegmentedControlPill<T extends string>({
  value,
  onChange,
  items,
  className,
  "aria-label": ariaLabel,
}: SegmentedControlBase<T>) {
  const cols = items.length;
  const idx = Math.max(0, items.findIndex((i) => i.value === value));
  const thumbWidth = cols <= 1 ? "100%" : cols === 2 ? "calc(50% - 4px)" : `calc(${100 / cols}% - 6px)`;
  const thumbStart =
    cols <= 1
      ? "4px"
      : cols === 2
        ? idx === 0
          ? "4px"
          : "calc(50% + 2px)"
        : `calc(${(100 / cols) * idx}% + 4px)`;

  return (
    <div
      className={cn(
        "relative grid w-full min-w-0 gap-0 bg-muted p-1",
        controlHeightClass,
        pillRadiusClass,
        className,
      )}
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={(e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        e.preventDefault();
        const next = (idx + (e.key === "ArrowRight" ? 1 : -1) + cols) % cols;
        onChange(items[next]!.value);
      }}
    >
      <div
        className={cn(
          "pointer-events-none absolute top-1 bottom-1 rounded-full bg-background shadow-sm transition-[inset-inline-start] duration-200 ease-out dark:bg-card",
        )}
        style={{ width: thumbWidth, insetInlineStart: thumbStart }}
        aria-hidden
      />
      {items.map((item) => {
        const selected = value === item.value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className={cn(
              "relative z-10 min-w-0 px-1 py-2 text-sm font-medium leading-snug transition-colors [overflow-wrap:anywhere]",
              pillRadiusClass,
              selected ? "text-foreground" : "text-foreground/70",
            )}
            onClick={() => onChange(item.value)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
