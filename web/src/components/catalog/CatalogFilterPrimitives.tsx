"use client";

import { useMemo, useState } from "react";
import { ChevronsUpDown, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { useLocaleContext } from "@/components/LocaleProvider";
import { scrollFocusedFieldIntoView } from "@/lib/focus-scroll";
import { cn } from "@/lib/utils";
import { colorSwatchClass, groupFacetRows } from "@/lib/catalog-client-utils";
import type { FacetRow } from "@/lib/types";

export function FacetMultiDropdown({
  label,
  rows,
  selected,
  onToggle,
  disabled,
  labelFormatter,
  comparator,
  testId,
}: {
  label: string;
  rows: FacetRow[];
  selected: Set<string>;
  onToggle: (values: string[]) => void;
  disabled?: boolean;
  labelFormatter?: (row: FacetRow) => string;
  comparator?: (a: string, b: string) => number;
  /** Стабильный селектор для e2e (catalog-facet-marks, …). */
  testId?: string;
}) {
  const { locale, t } = useLocaleContext();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const groupedRows = useMemo(() => groupFacetRows(rows, { labelFormatter, comparator }), [rows, labelFormatter, comparator]);
  const filtered = useMemo(
    () =>
      !q.trim()
        ? groupedRows
        : groupedRows.filter((r) => r.label.toLowerCase().includes(q.trim().toLowerCase())),
    [groupedRows, q],
  );
  const n = groupedRows.filter((r) => r.values.some((v) => selected.has(v))).length;
  return (
    <DropdownMenu
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQ("");
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled || !groupedRows.length}
          className="h-10 w-full justify-between gap-2 rounded-lg px-3.5 font-normal"
          data-testid={testId}
          aria-label={
            n > 0
              ? t("catalog.facets.facetAriaSelected", { label, n: String(n) })
              : t("catalog.facets.facetAria", { label })
          }
        >
          <span className="min-w-0 text-start [overflow-wrap:anywhere]">
            {label}
            {n > 0 ? (
              <span className="ms-1 tabular-nums text-muted-foreground">({n})</span>
            ) : null}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-50" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="max-h-[min(24rem,70vh)] w-[var(--radix-dropdown-menu-trigger-width)] min-w-[12rem] overflow-hidden p-0 shadow-lg"
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <div className="border-b border-border p-2">
          <Input
            placeholder={t("catalog.facets.search")}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-10 rounded-lg"
            onFocus={(e) => scrollFocusedFieldIntoView(e.currentTarget)}
            onPointerDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          />
        </div>
        <DropdownMenuLabel className="px-3 py-2 text-xs font-normal text-muted-foreground">
          {t("catalog.facets.multiHint")}
        </DropdownMenuLabel>
        <div className="max-h-60 overflow-y-auto overscroll-contain p-1.5 pt-0">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">{t("catalog.facets.noMatches")}</p>
          ) : (
            filtered.map((r) => (
              <DropdownMenuCheckboxItem
                key={r.label}
                checked={r.values.some((v) => selected.has(v))}
                onCheckedChange={() => onToggle(r.values)}
                className="cursor-text rounded-xl select-text [&>span:last-child]:ps-2"
              >
                <span className="min-w-0 flex-1 select-text [overflow-wrap:anywhere]">{r.label}</span>
                <span className="ms-1 shrink-0 tabular-nums text-xs text-muted-foreground">
                  {r.count.toLocaleString(locale === "en" ? "en-US" : "ru-RU")}
                </span>
              </DropdownMenuCheckboxItem>
            ))
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function ColorFacetDialog({
  label,
  rows,
  selected,
  onToggle,
  disabled,
  labelFormatter,
  testId,
}: {
  label: string;
  rows: FacetRow[];
  selected: Set<string>;
  onToggle: (values: string[]) => void;
  disabled?: boolean;
  labelFormatter?: (row: FacetRow) => string;
  testId?: string;
}) {
  const { locale, t } = useLocaleContext();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const groupedRows = useMemo(() => groupFacetRows(rows, { labelFormatter }), [rows, labelFormatter]);
  const filtered = useMemo(
    () =>
      !q.trim()
        ? groupedRows
        : groupedRows.filter((r) => r.label.toLowerCase().includes(q.trim().toLowerCase())),
    [groupedRows, q],
  );
  const n = groupedRows.filter((r) => r.values.some((v) => selected.has(v))).length;

  return (
    <div className="min-w-0">
      {/* Заголовок-триггер */}
      <button
        type="button"
        disabled={disabled || !groupedRows.length}
        data-testid={testId}
        aria-expanded={open}
        aria-label={
          n > 0
            ? t("catalog.facets.colorAriaSelected", { label, n: String(n) })
            : t("catalog.facets.colorAria", { label })
        }
        className="flex h-10 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-3.5 text-sm disabled:cursor-not-allowed disabled:opacity-50 hover:bg-accent"
        onClick={() => {
          setOpen((v) => !v);
          if (open) setQ("");
        }}
      >
        <span className="min-w-0 text-start [overflow-wrap:anywhere]">
          {label}
          {n > 0 ? (
            <span className="ms-1 tabular-nums text-muted-foreground">({n})</span>
          ) : null}
        </span>
        <LayoutGrid className="size-4 shrink-0 opacity-50" aria-hidden />
      </button>

      {/* Inline-раскрывающаяся панель */}
      {open ? (
        <div className="mt-2 min-w-0 rounded-xl border border-border bg-background shadow-sm">
          {/* Поиск */}
          <div className="border-b border-border px-3 py-2">
            <Input
              placeholder={t("catalog.facets.colorSearch")}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="h-8 rounded-lg text-sm"
            />
          </div>

          {/* Сетка цветов */}
          <div className="max-h-[min(22rem,55vh)] overflow-y-auto overscroll-contain px-3 py-3 [scrollbar-width:thin]">
            {filtered.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">
                {t("catalog.facets.noMatches")}
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-1.5">
                {filtered.map((r) => {
                  const active = r.values.some((v) => selected.has(v));
                  return (
                    <button
                      key={r.label}
                      type="button"
                      onClick={() => onToggle(r.values)}
                      className={cn(
                        "flex min-w-0 flex-col items-center gap-1 rounded-lg px-2 py-2 text-center transition-colors",
                        active
                          ? "bg-primary/10 ring-1 ring-primary"
                          : "hover:bg-muted",
                      )}
                    >
                      <span
                        className={cn(
                          "size-5 shrink-0 rounded-full border border-border/50",
                          colorSwatchClass(r.label),
                        )}
                        aria-hidden
                      />
                      <span className="w-full truncate text-[11px] leading-tight text-foreground">
                        {r.label}
                      </span>
                      <span className="tabular-nums text-[10px] text-muted-foreground">
                        {r.count.toLocaleString(locale === "en" ? "en-US" : "ru-RU")}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Нижняя строка */}
          <div className="flex items-center justify-between border-t border-border px-3 py-2">
            {n > 0 ? (
              <button
                type="button"
                className="text-xs text-muted-foreground hover:text-foreground"
                onClick={() => groupedRows.filter((r) => r.values.some((v) => selected.has(v))).forEach((r) => onToggle(r.values))}
              >
                {t("catalog.facets.colorClearAll")}
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              className="text-xs font-medium text-primary hover:underline"
              onClick={() => { setOpen(false); setQ(""); }}
            >
              {t("catalog.facets.close")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
