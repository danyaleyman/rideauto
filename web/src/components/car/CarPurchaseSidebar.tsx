"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, ExternalLink, Heart, Plus } from "lucide-react";
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
    <aside
      id="car-order-panel"
      className="relative max-w-full overflow-hidden rounded-2xl border border-border/70 bg-card p-4 shadow-md ring-1 ring-black/[0.04] dark:ring-white/[0.08] sm:rounded-3xl sm:p-6 lg:sticky lg:top-24"
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-blue-600 via-sky-500 to-cyan-500"
        aria-hidden
      />
      <h2 className="sr-only">Цена и заказ</h2>
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Оценка в каталоге</p>
      <p className="mt-1 break-words text-2xl font-bold leading-tight tracking-tight text-foreground [overflow-wrap:anywhere] tabular-nums sm:text-3xl md:text-[2rem]">
        {priceRub != null && !Number.isNaN(priceRub) ? formatPriceLabel(priceRub) : formatPriceLabel(null)}
      </p>
      <p className="mt-3 line-clamp-3 text-sm font-semibold leading-snug text-foreground sm:line-clamp-2">
        {title}
      </p>
      <p className="mt-2 font-mono text-xs tabular-nums text-muted-foreground">ID · {carId}</p>
      {sourceLabel ? (
        <Badge variant="secondary" className="mt-3 rounded-full px-3 py-1 text-xs font-medium">
          Источник · {sourceLabel}
        </Badge>
      ) : null}

      <div className="mt-5 flex min-w-0 flex-wrap gap-2">
        {sourceUrl ? (
          <Button variant="outline" size="icon-sm" className="rounded-xl shadow-sm" asChild>
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" title="Оригинал объявления">
              <span className="sr-only">Оригинал объявления</span>
              <ExternalLink className="size-4" aria-hidden />
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

      <div className="mt-6 flex flex-col gap-2.5">
        <Button
          className="h-11 w-full rounded-xl bg-blue-600 text-[15px] font-semibold text-white shadow-sm hover:bg-blue-700"
          asChild
        >
          <Link href="/contacts">Связаться с менеджером</Link>
        </Button>

        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" className="h-11 w-full rounded-xl border-border/80 font-medium shadow-sm">
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

      <div className="mt-6 rounded-2xl border border-dashed border-border/60 bg-muted/25 px-3 py-3">
        <p className="flex items-center gap-2 text-xs leading-relaxed text-muted-foreground">
          <Heart className="size-3.5 shrink-0 text-blue-600/80 dark:text-sky-400" aria-hidden />
          Подбор, доставка и оформление — World Ride Auto
        </p>
      </div>
    </aside>
  );
}
