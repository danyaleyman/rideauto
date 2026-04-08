"use client";

import Link from "next/link";
import { Bookmark, Heart, Trash2 } from "lucide-react";
import { useFavorites } from "@/hooks/use-favorites";
import { formatPriceLabel } from "@/lib/format-price";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

export function FavoritesDialog() {
  const { items, count, remove } = useFavorites();

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="relative rounded-full shadow-sm"
          aria-label={
            count > 0 ? `Избранное, ${count} авто` : "Избранное"
          }
        >
          <Heart className="size-4 opacity-80" />
          <span className="ms-1.5 hidden sm:inline">Избранное</span>
          {count > 0 ? (
            <span className="absolute -top-1.5 -end-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground shadow">
              {count > 99 ? "99+" : count}
            </span>
          ) : null}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] gap-4 sm:max-w-md" showCloseButton>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Bookmark className="size-5 opacity-70" />
            Избранные авто
          </DialogTitle>
          <DialogDescription>
            Сохранено в этом браузере. Нажмите на строку, чтобы открыть карточку.
          </DialogDescription>
        </DialogHeader>
        {count === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Пока пусто. В каталоге нажмите «+» на карточке, чтобы добавить объявление.
          </p>
        ) : (
          <ScrollArea className="max-h-[min(50vh,360px)] pr-3">
            <ul className="space-y-2">
              {items
                .slice()
                .sort((a, b) => b.addedAt - a.addedAt)
                .map((car) => (
                  <li
                    key={car.id}
                    className="flex items-start gap-2 rounded-2xl border border-border/80 bg-muted/20 p-3 text-sm shadow-sm"
                  >
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/car/${encodeURIComponent(car.id)}`}
                        className="font-medium text-foreground underline-offset-4 hover:underline"
                      >
                        {car.title}
                      </Link>
                      <p className="mt-0.5 tabular-nums text-xs text-muted-foreground">
                        {formatPriceLabel(car.price)}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-xs"
                      className="shrink-0 text-muted-foreground hover:text-destructive"
                      title="Убрать из избранного"
                      aria-label="Убрать из избранного"
                      onClick={() => remove(car.id)}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </li>
                ))}
            </ul>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
