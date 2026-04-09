"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, Heart, Plus } from "lucide-react";
import { useFavorites } from "@/hooks/use-favorites";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { formatPriceLabel } from "@/lib/format-price";
import { formatKrw } from "@/lib/car-detail-data";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import type { SlimCar } from "@/lib/types";

type Props = {
  carId: string;
  title: string;
  priceRub: number | null;
  sourceUrl: string | null;
  /** Сырые поля для модалки расчёта */
  priceWon: number | null;
  priceCny: number | null;
  sourceLabel: string | null;
};

function slimForFavorite(
  id: string,
  title: string,
  price: number | null,
): SlimCar {
  return {
    id,
    title,
    price,
    data: {},
  };
}

export function CarPurchaseSidebar({
  carId,
  title,
  priceRub,
  sourceUrl,
  priceWon,
  priceCny,
  sourceLabel,
}: Props) {
  const { toggle, isFavorite } = useFavorites();
  const fav = isFavorite(carId);
  const [copied, setCopied] = useState(false);

  const breakdownRows: { label: string; value: string; note?: string }[] = [];
  if (priceRub != null && !Number.isNaN(priceRub)) {
    breakdownRows.push({
      label: "Стоимость автомобиля (оценка в каталоге)",
      value: formatPriceLabel(priceRub),
    });
  }
  if (priceWon != null && !Number.isNaN(priceWon)) {
    breakdownRows.push({
      label: "Цена на площадке (источник)",
      value: formatKrw(priceWon),
    });
  }
  if (priceCny != null && !Number.isNaN(priceCny)) {
    breakdownRows.push({
      label: "Цена в CNY (если применимо)",
      value: `${Math.round(priceCny).toLocaleString("ru-RU")} CN¥`,
    });
  }

  return (
    <aside className="rounded-2xl border border-border/80 bg-card p-5 shadow-lg ring-1 ring-black/5 dark:ring-white/10 lg:sticky lg:top-20">
      <h2 className="sr-only">Цена и заказ</h2>
      <p className="text-3xl font-bold tabular-nums tracking-tight text-foreground">
        {priceRub != null && !Number.isNaN(priceRub) ? formatPriceLabel(priceRub) : formatPriceLabel(null)}
      </p>
      <p className="mt-2 line-clamp-2 text-sm font-medium leading-snug text-foreground/90">{title}</p>
      <p className="mt-1 text-xs text-muted-foreground">ID: {carId}</p>
      {sourceLabel ? (
        <Badge variant="secondary" className="mt-3 rounded-lg px-2.5 py-0.5 text-xs font-normal">
          Источник: {sourceLabel}
        </Badge>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        {sourceUrl ? (
          <Button variant="outline" size="icon-sm" className="rounded-xl shadow-sm" asChild>
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" title="Оригинал объявления">
              <span className="sr-only">Оригинал</span>
              <span aria-hidden className="text-xs font-semibold">
                ↗
              </span>
            </a>
          </Button>
        ) : null}
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className="rounded-xl shadow-sm"
          title={copied ? "Скопировано" : "Копировать ссылку"}
          onClick={() => {
            void navigator.clipboard.writeText(getCarPageAbsoluteUrl(carId)).then(() => {
              setCopied(true);
              window.setTimeout(() => setCopied(false), 2000);
            });
          }}
        >
          {copied ? <Check className="size-4 text-green-600" /> : <Copy className="size-4" />}
        </Button>
        <Button
          type="button"
          variant={fav ? "default" : "outline"}
          size="icon-sm"
          className="rounded-xl shadow-sm"
          title={fav ? "В избранном" : "В избранное"}
          aria-pressed={fav}
          onClick={() => toggle(slimForFavorite(carId, title, priceRub))}
        >
          {fav ? <Check className="size-4" /> : <Plus className="size-4" />}
        </Button>
      </div>

      <div className="mt-5 flex flex-col gap-2">
        <Button className="w-full rounded-xl bg-blue-600 font-semibold text-white hover:bg-blue-700" asChild>
          <Link href="/contacts">Связаться с менеджером</Link>
        </Button>

        <Dialog>
          <DialogTrigger asChild>
            <Button variant="secondary" className="w-full rounded-xl">
              Подробный расчёт
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[min(90vh,40rem)] overflow-y-auto sm:max-w-lg" showCloseButton>
            <DialogHeader>
              <DialogTitle>Состав цены</DialogTitle>
              <DialogDescription>
                Ниже только те суммы, которые есть в карточке. Расходы на логистику, таможню и услуги компании
                фиксируются индивидуально.
              </DialogDescription>
            </DialogHeader>
            {breakdownRows.length === 0 ? (
              <p className="text-sm text-muted-foreground">Нет числовых данных для расчёта в объявлении.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {breakdownRows.map((row) => (
                  <li
                    key={row.label}
                    className="flex flex-col gap-0.5 rounded-xl border border-border/60 bg-muted/25 px-3 py-2"
                  >
                    <span className="text-muted-foreground">{row.label}</span>
                    <span className="font-semibold tabular-nums text-foreground">{row.value}</span>
                    {row.note ? <span className="text-xs text-muted-foreground">{row.note}</span> : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-muted-foreground">
              Итог «под ключ» и сроки — уточняйте у менеджера: мы учитываем курс, маршрут и комплектацию.
            </p>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mt-4 border-t border-border pt-4">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Heart className="size-3.5 shrink-0 opacity-70" aria-hidden />
          Подбор и доставка — World Ride Auto
        </p>
      </div>
    </aside>
  );
}
