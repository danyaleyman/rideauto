"use client";

import { useMemo, useState } from "react";
import { ChevronsUpDown, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
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
}: {
  label: string;
  rows: FacetRow[];
  selected: Set<string>;
  onToggle: (values: string[]) => void;
  disabled?: boolean;
  labelFormatter?: (row: FacetRow) => string;
  comparator?: (a: string, b: string) => number;
}) {
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
          className="h-10 w-full justify-between gap-2 rounded-2xl px-3.5 font-normal"
          aria-label={
            n > 0 ? `${label}, фильтр, выбрано значений: ${n}, открыть список` : `${label}, фильтр, открыть список`
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
            placeholder="Поиск…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-8 rounded-xl"
            onPointerDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          />
        </div>
        <DropdownMenuLabel className="px-3 py-2 text-xs font-normal text-muted-foreground">
          Можно выбрать несколько
        </DropdownMenuLabel>
        <div className="max-h-60 overflow-y-auto overscroll-contain p-1.5 pt-0">
          {filtered.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-muted-foreground">Нет совпадений</p>
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
                  {r.count.toLocaleString("ru-RU")}
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
}: {
  label: string;
  rows: FacetRow[];
  selected: Set<string>;
  onToggle: (values: string[]) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const groupedRows = useMemo(() => groupFacetRows(rows), [rows]);
  const filtered = useMemo(
    () =>
      !q.trim()
        ? groupedRows
        : groupedRows.filter((r) => r.label.toLowerCase().includes(q.trim().toLowerCase())),
    [groupedRows, q],
  );
  const n = groupedRows.filter((r) => r.values.some((v) => selected.has(v))).length;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQ("");
      }}
    >
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled || !groupedRows.length}
          className="h-10 w-full justify-between gap-2 rounded-2xl px-3.5 font-normal"
          aria-label={
            n > 0
              ? `${label}, фильтр по цвету, выбрано значений: ${n}, открыть`
              : `${label}, фильтр по цвету, открыть`
          }
        >
          <span className="min-w-0 text-start [overflow-wrap:anywhere]">
            {label}
            {n > 0 ? (
              <span className="ms-1 tabular-nums text-muted-foreground">({n})</span>
            ) : null}
          </span>
          <LayoutGrid className="size-4 shrink-0 opacity-50" aria-hidden />
        </Button>
      </DialogTrigger>
      <DialogContent
        showCloseButton
        className="flex max-h-[90vh] w-[min(96vw,56rem)] max-w-[min(96vw,56rem)] flex-col gap-0 overflow-hidden p-0 sm:w-[min(96vw,64rem)] sm:max-w-[min(96vw,64rem)]"
      >
        <DialogHeader className="shrink-0 space-y-1 border-b border-border px-5 pt-5 pb-3 pe-12 sm:px-6 sm:pt-6 sm:pb-4 sm:pe-14">
          <DialogTitle className="text-base sm:text-lg">{label}</DialogTitle>
          <DialogDescription>Можно выбрать несколько значений</DialogDescription>
        </DialogHeader>
        <div className="shrink-0 border-b border-border px-5 py-3 sm:px-6">
          <Input
            placeholder="Поиск по названию цвета…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="h-10 rounded-xl text-sm"
          />
        </div>
        <div
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-4 sm:px-6 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
        >
          {filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Нет совпадений</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {filtered.map((r) => {
                const active = r.values.some((v) => selected.has(v));
                return (
                  <div key={r.label} className="min-w-0">
                    <Button
                      type="button"
                      variant={active ? "default" : "outline"}
                      size="sm"
                      className="h-auto min-h-11 w-full min-w-0 flex-col items-stretch justify-center gap-1 rounded-xl px-3 py-2.5 text-center font-normal shadow-sm"
                      onClick={() => onToggle(r.values)}
                    >
                      <span
                        className={cn(
                          "mx-auto size-4 shrink-0 rounded-full",
                          colorSwatchClass(r.label),
                        )}
                        aria-hidden
                      />
                      <span className="min-w-0 text-pretty text-xs leading-snug sm:text-[13px]">{r.label}</span>
                      <span className="tabular-nums text-[11px] text-muted-foreground">
                        {r.count.toLocaleString("ru-RU")}
                      </span>
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <DialogFooter className="shrink-0 border-t border-border px-6 py-4">
          <DialogClose asChild>
            <Button type="button" variant="secondary" className="w-full sm:w-auto">
              Закрыть
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
