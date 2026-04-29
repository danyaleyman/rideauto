"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { Check, Copy, ExternalLink, Heart } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { useFavorites } from "@/hooks/use-favorites";
import { getCarPageAbsoluteUrl } from "@/lib/car-url";
import { formatPriceLabel, PRICE_ON_REQUEST_RU } from "@/lib/format-price";
import { formatHumanDate, formatKrw } from "@/lib/car-detail-data";
import { Button } from "@/components/ui/button";
import { CatalogQuickBuyDialog } from "@/components/catalog/CatalogQuickBuyDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { MOTION_PRESETS, MOTION_TOKENS } from "@/components/ui/motion";
import type { SlimCar } from "@/lib/types";

type Props = {
  carId: string;
  title: string;
  priceRub: number | null;
  priceOnRequest?: boolean;
  sourceUrl: string | null;
  /** Сырые поля для модалки расчёта */
  priceWon: number | null;
  priceCny: number | null;
  sourceLabel: string | null;
  catalogCreatedAt?: string | null;
  sourceUpdatedAt?: string | null;
  calcDetails?: Record<string, unknown> | null;
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
  priceOnRequest = false,
  sourceUrl,
  priceWon,
  priceCny,
  sourceLabel,
  catalogCreatedAt,
  sourceUpdatedAt,
  calcDetails,
}: Props) {
  const reduceMotion = useReducedMotion();
  const { authenticated } = useAuth();
  const { toggle, isFavorite } = useFavorites();
  const fav = authenticated && isFavorite(carId);
  const [copied, setCopied] = useState(false);

  const breakdownRows: { label: string; value: string; note?: string; subRows?: { label: string; value: string }[] }[] = [];
  const num = (v: unknown): number | null => {
    if (v == null || v === "") return null;
    const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, "").replace(",", "."));
    if (!Number.isFinite(n)) return null;
    return n;
  };
  if (!priceOnRequest && priceRub != null && !Number.isNaN(priceRub)) {
    breakdownRows.push({
      label: "Стоимость в России под ключ",
      value: formatPriceLabel(priceRub),
    });
  }
  if (priceWon != null && !Number.isNaN(priceWon)) {
    const wonTotal = priceWon >= 100000 ? priceWon : priceWon * 10000;
    breakdownRows.push({
      label: "Цена на площадке Encar",
      value: `${Math.round(wonTotal).toLocaleString("ru-RU")} ₩ (Вон)`,
    });
  }
  if (priceCny != null && !Number.isNaN(priceCny)) {
    breakdownRows.push({
      label: "Цена в CNY (если применимо)",
      value: `${Math.round(priceCny).toLocaleString("ru-RU")} CN¥`,
    });
  }
  const duty = num(calcDetails?.duty_rub);
  const customsFee = num(calcDetails?.customs_fee_rub);
  const util = num(calcDetails?.util_rub);
  const excise = num(calcDetails?.excise_rub);
  const vat = num(calcDetails?.vat_rub);
  const customsTotal = num(calcDetails?.customs_total_rub);
  const freight = num(calcDetails?.freight_rub);
  const docs = num(calcDetails?.documents_krw_rub) ?? num(calcDetails?.china_docs_delivery_rub);
  const broker = num(calcDetails?.broker_rub);
  const commission = num(calcDetails?.commission_rub);

  breakdownRows.push({
    label: "Таможенные расходы",
    value: customsTotal != null ? formatPriceLabel(customsTotal) : "—",
    subRows: [
      { label: "Пошлина", value: duty != null ? formatPriceLabel(duty) : "—" },
      { label: "Таможенный сбор", value: customsFee != null ? formatPriceLabel(customsFee) : "—" },
      { label: "Утилизационный сбор", value: util != null ? formatPriceLabel(util) : "—" },
      { label: "Акциз", value: excise != null ? formatPriceLabel(excise) : "—" },
      { label: "НДС", value: vat != null ? formatPriceLabel(vat) : "—" },
    ],
  });
  breakdownRows.push({
    label: "Логистика и портовые расходы",
    value: freight != null ? formatPriceLabel(freight) : "—",
    subRows: [{ label: "Доставка / порт", value: freight != null ? formatPriceLabel(freight) : "—" }],
  });
  breakdownRows.push({
    label: "Брокерская комиссия",
    value: broker != null ? formatPriceLabel(broker) : "—",
    subRows: [
      { label: "Брокер", value: broker != null ? formatPriceLabel(broker) : "—" },
      { label: "Комиссия", value: commission != null ? formatPriceLabel(commission) : "—" },
    ],
  });
  breakdownRows.push({
    label: "СБКТС / ЭПТС / регистрационные платежи",
    value: docs != null ? formatPriceLabel(docs) : "—",
  });

  const updatedLabel = formatHumanDate(sourceUpdatedAt);
  const createdLabel = formatHumanDate(catalogCreatedAt);

  return (
    <motion.aside
      id="car-order-panel"
      className="relative max-w-full overflow-hidden rounded-2xl border border-border/70 bg-card p-4 shadow-md ring-1 ring-black/[0.04] dark:ring-white/[0.08] sm:rounded-3xl sm:p-6 lg:sticky lg:top-24"
      initial={reduceMotion ? false : { opacity: 0, y: MOTION_TOKENS.offsets.fadeUpSm }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={reduceMotion ? { duration: 0.01 } : { duration: 0.3, ease: MOTION_TOKENS.easeSoft }}
    >
      <h2 className="sr-only">Цена и заказ</h2>
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Стоимость в России под ключ</p>
      <p className="mt-1 break-words text-2xl font-bold leading-tight tracking-tight text-foreground [overflow-wrap:anywhere] tabular-nums sm:text-3xl md:text-[2rem]">
        {priceOnRequest ? PRICE_ON_REQUEST_RU : priceRub != null && !Number.isNaN(priceRub) ? formatPriceLabel(priceRub) : PRICE_ON_REQUEST_RU}
      </p>
      <p className="mt-3 line-clamp-3 text-sm font-semibold leading-snug text-foreground sm:line-clamp-2">
        {title}
      </p>
      {(updatedLabel || createdLabel) ? (
        <div className="mt-2 space-y-1 text-xs text-muted-foreground">
          {updatedLabel ? <p>Обновлено: {updatedLabel}</p> : null}
          {createdLabel ? <p>Добавлено в каталог: {createdLabel}</p> : null}
        </div>
      ) : null}
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
        {authenticated ? (
          <Button
            type="button"
            variant={fav ? "default" : "outline"}
            size="icon-sm"
            className="rounded-xl shadow-sm"
            title={fav ? "В избранном" : "В избранное"}
            aria-pressed={fav}
            onClick={() => {
              void toggle(slimForFavorite(carId, title, priceRub));
            }}
          >
            <Heart className={fav ? "size-4 fill-current" : "size-4"} />
          </Button>
        ) : null}
      </div>

      <div className="mt-6 flex flex-col gap-2.5">
        <CatalogQuickBuyDialog
          carId={carId}
          carTitle={title}
          triggerLabel="Купить автомобиль"
          triggerSize="default"
          triggerClassName="h-11 w-full rounded-xl bg-red-600 text-[15px] font-semibold text-white shadow-sm hover:bg-red-700"
        />
        <motion.div {...(reduceMotion ? {} : MOTION_PRESETS.pressable)}>
          <Button
            className="h-11 w-full rounded-xl bg-blue-600 text-[15px] font-semibold text-white shadow-sm hover:bg-blue-700"
            asChild
          >
            <Link href="/contacts">Связаться с менеджером</Link>
          </Button>
        </motion.div>

        <Dialog>
          <DialogTrigger asChild>
            <motion.div {...(reduceMotion ? {} : MOTION_PRESETS.pressable)}>
              <Button variant="outline" className="h-11 w-full rounded-xl border-border/80 font-medium shadow-sm">
                Подробный расчёт
              </Button>
            </motion.div>
          </DialogTrigger>
          <DialogContent className="max-h-[min(90vh,40rem)] overflow-y-auto sm:max-w-lg" showCloseButton>
            <DialogHeader>
              <DialogTitle>Состав цены</DialogTitle>
              <DialogDescription>
                Расчет показывает полную структуру стоимости под ключ. Точные суммы сервисных и логистических статей
                зависят от маршрута и фиксируются менеджером.
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
                    {row.subRows && row.subRows.length > 0 ? (
                      <ul className="mt-1 space-y-1.5 border-t border-border/50 pt-2">
                        {row.subRows.map((sub) => (
                          <li key={`${row.label}-${sub.label}`} className="flex items-center justify-between gap-3 text-xs">
                            <span className="text-muted-foreground">{sub.label}</span>
                            <span className="font-medium tabular-nums text-foreground">{sub.value}</span>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-muted-foreground">Суммы формируются автоматически по данным калькулятора для конкретного авто.</p>
          </DialogContent>
        </Dialog>
      </div>
    </motion.aside>
  );
}
