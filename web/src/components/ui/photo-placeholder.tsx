import { cn } from "@/lib/utils";

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
        "flex w-full items-end bg-muted px-3 py-2 text-muted-foreground",
        ratioClass,
        className,
      )}
      aria-hidden
    >
      <p className="text-[11px] leading-snug">{label}</p>
    </div>
  );
}
