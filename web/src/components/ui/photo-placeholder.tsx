import { cn } from "@/lib/utils";
import { ImageIcon } from "lucide-react";

/** Серая плашка под будущее фото. Не декорация — слот контента. */
export function PhotoPlaceholder({
  label,
  className,
  ratioClass = "aspect-[16/10]",
}: {
  label: string;
  className?: string;
  ratioClass?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex w-full items-end overflow-hidden bg-muted p-3",
        ratioClass,
        className,
      )}
      aria-hidden
    >
      {/* Деликатный диагональный градиент — не выбивается из нейтральной палитры. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-br from-transparent to-foreground/5"
      />
      <ImageIcon
        className="pointer-events-none absolute left-1/2 top-1/2 size-6 -translate-x-1/2 -translate-y-1/2 text-muted-foreground/30"
        aria-hidden
      />
      <p className="relative text-[11px] font-medium leading-snug text-muted-foreground/80">{label}</p>
    </div>
  );
}
