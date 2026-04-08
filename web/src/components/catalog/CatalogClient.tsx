"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  catalogStateKey,
  parseCatalogUrl,
  PER_PAGE,
  stateToBrowserUrl,
  type CatalogUrlState,
  toApiSearchParams,
  toFacetApiParams,
} from "@/lib/catalog-url";
import { fetchFacetsClient, fetchSearchClient } from "@/lib/client-api";
import { extractCarImageUrls } from "@/lib/car-images";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { FacetRow, FacetsResponse, SearchResponse, SlimCar } from "@/lib/types";

function formatPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: "RUB",
      maximumFractionDigits: 0,
    }).format(n);
  } catch {
    return `${n} ₽`;
  }
}

function firstImageUrl(car: SlimCar): string | undefined {
  return extractCarImageUrls((car.data ?? {}) as Record<string, unknown>)[0];
}

function metaText(car: SlimCar): string {
  const d = car.data ?? {};
  const parts: string[] = [];
  const mark = typeof d.mark === "string" ? d.mark.trim() : "";
  const model = typeof d.model === "string" ? d.model.trim() : "";
  if (mark || model) parts.push([mark, model].filter(Boolean).join(" "));
  const km = d.km_age;
  if (typeof km === "number" && Number.isFinite(km)) {
    parts.push(`${km.toLocaleString("ru-RU")} км`);
  } else if (typeof km === "string" && km.trim()) {
    parts.push(`${km.trim()} км`);
  }
  return parts.join(" · ");
}

function FacetGroup({
  title,
  rows,
  selected,
  onToggle,
}: {
  title: string;
  rows: FacetRow[];
  selected: Set<string>;
  onToggle: (v: string) => void;
}) {
  if (!rows.length) return null;
  return (
    <fieldset className="rounded-xl border border-border bg-muted/25 p-3">
      <legend className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </legend>
      <div className="max-h-44 space-y-1 overflow-y-auto pr-1 text-sm">
        {rows.map((r) => (
          <label
            key={r.value}
            className="flex cursor-pointer items-center gap-2 rounded-lg px-1 py-0.5 hover:bg-muted/50"
          >
            <input
              type="checkbox"
              checked={selected.has(r.value)}
              onChange={() => onToggle(r.value)}
              className="size-3.5 rounded border-border accent-primary"
            />
            <span className="min-w-0 flex-1 truncate" title={r.value}>
              {r.value}
            </span>
            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
              {r.count.toLocaleString("ru-RU")}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function FacetSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-muted/25 p-3">
      <div className="mb-2 h-4 w-24 rounded bg-muted" />
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-muted" />
        <div className="h-4 w-5/6 rounded bg-muted" />
        <div className="h-4 w-4/6 rounded bg-muted" />
      </div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <li className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <div className="aspect-[16/10] animate-pulse bg-muted" />
      <div className="space-y-2 p-4">
        <div className="h-4 w-11/12 animate-pulse rounded bg-muted" />
        <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
        <div className="h-6 w-2/5 animate-pulse rounded bg-muted" />
      </div>
    </li>
  );
}

function RangeBlock({
  state,
  navigate,
}: {
  state: CatalogUrlState;
  navigate: (s: CatalogUrlState) => void;
}) {
  const [draft, setDraft] = useState({
    price_from: state.price_from,
    price_to: state.price_to,
    mileage_from: state.mileage_from,
    mileage_to: state.mileage_to,
    year_from: state.year_from,
    year_to: state.year_to,
  });
  useEffect(() => {
    setDraft({
      price_from: state.price_from,
      price_to: state.price_to,
      mileage_from: state.mileage_from,
      mileage_to: state.mileage_to,
      year_from: state.year_from,
      year_to: state.year_to,
    });
  }, [
    state.price_from,
    state.price_to,
    state.mileage_from,
    state.mileage_to,
    state.year_from,
    state.year_to,
  ]);
  const apply = () => {
    navigate({
      ...state,
      ...draft,
      page: 1,
    });
  };
  return (
    <>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <Input
          placeholder="Цена от"
          value={draft.price_from}
          onChange={(e) => setDraft((d) => ({ ...d, price_from: e.target.value }))}
        />
        <Input
          placeholder="Цена до"
          value={draft.price_to}
          onChange={(e) => setDraft((d) => ({ ...d, price_to: e.target.value }))}
        />
        <Input
          placeholder="Пробег от"
          value={draft.mileage_from}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_from: e.target.value }))}
        />
        <Input
          placeholder="Пробег до"
          value={draft.mileage_to}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_to: e.target.value }))}
        />
        <Input
          placeholder="Год от"
          value={draft.year_from}
          onChange={(e) => setDraft((d) => ({ ...d, year_from: e.target.value }))}
        />
        <Input
          placeholder="Год до"
          value={draft.year_to}
          onChange={(e) => setDraft((d) => ({ ...d, year_to: e.target.value }))}
        />
      </div>
      <Button type="button" onClick={apply} className="mt-2 w-full" size="sm">
        Применить диапазоны
      </Button>
    </>
  );
}

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "date_new", label: "Сначала новые" },
  { value: "date_old", label: "Сначала старые" },
  { value: "year_new", label: "Год: новее" },
  { value: "year_old", label: "Год: старше" },
  { value: "price_low", label: "Цена: дешевле" },
  { value: "price_high", label: "Цена: дороже" },
  { value: "mileage_low", label: "Пробег: меньше" },
  { value: "mileage_high", label: "Пробег: больше" },
];

export function CatalogClient({
  initialSearch,
  ssrKey,
}: {
  initialSearch: SearchResponse;
  ssrKey: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  const spStr = sp.toString();
  const state = useMemo(() => parseCatalogUrl(new URLSearchParams(spStr)), [spStr]);
  const key = useMemo(() => catalogStateKey(state), [state]);

  const [search, setSearch] = useState<SearchResponse>(initialSearch);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [qDraft, setQDraft] = useState(state.q);
  const facetsCacheRef = useRef<Map<string, FacetsResponse>>(new Map());

  useEffect(() => {
    setQDraft(state.q);
  }, [state.q]);

  useEffect(() => {
    if (!spStr.trim()) {
      const qs = stateToBrowserUrl(parseCatalogUrl(new URLSearchParams()));
      router.replace(`/catalog?${qs}`, { scroll: false });
    }
  }, [spStr, router]);

  const navigate = useCallback(
    (next: CatalogUrlState) => {
      const qs = stateToBrowserUrl(next);
      router.push(qs ? `/catalog?${qs}` : "/catalog", { scroll: false });
    },
    [router],
  );

  useEffect(() => {
    const nextQ = qDraft.trim();
    if (nextQ === state.q) return;
    if (nextQ.length > 0 && nextQ.length < 2) return;
    const t = window.setTimeout(() => {
      navigate({ ...state, q: nextQ, page: 1 });
    }, 450);
    return () => window.clearTimeout(t);
  }, [qDraft, state, navigate]);

  const facetState = useMemo(
    () => ({
      ...state,
      page: 1,
      // Facets are independent from sort; avoid refetch on sort switch.
      sort: "date_new",
    }),
    [state],
  );
  const facetKey = useMemo(() => catalogStateKey(facetState), [facetState]);

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        setErr(null);
        setLoading(true);
        const sq = toApiSearchParams(state);
        const searchP =
          key === ssrKey
            ? Promise.resolve(initialSearch)
            : fetchSearchClient(sq, { signal: ac.signal });
        const sRes = await searchP;
        if (ac.signal.aborted) return;
        setSearch(sRes);
      } catch (e) {
        if (ac.signal.aborted) return;
        setErr(e instanceof Error ? e.message : "Ошибка загрузки");
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    })();
    return () => {
      ac.abort();
    };
  }, [key, ssrKey, state, initialSearch]);

  useEffect(() => {
    const cached = facetsCacheRef.current.get(facetKey);
    if (cached) {
      setFacets(cached);
      return;
    }
    const ac = new AbortController();
    (async () => {
      try {
        const fq = toFacetApiParams(facetState);
        const fRes = await fetchFacetsClient(fq, { signal: ac.signal });
        if (ac.signal.aborted) return;
        facetsCacheRef.current.set(facetKey, fRes);
        setFacets(fRes);
      } catch {
        // Keep previous facets silently on transient facet errors.
      }
    })();
    return () => ac.abort();
  }, [facetKey, facetState]);

  const toggle = (field: keyof CatalogUrlState, value: string) => {
    const cur = state[field];
    if (!Array.isArray(cur)) return;
    const arr = [...cur];
    const i = arr.indexOf(value);
    if (i >= 0) arr.splice(i, 1);
    else arr.push(value);
    navigate({ ...state, [field]: arr, page: 1 });
  };

  const reset = () => {
    navigate({
      market: state.market,
      q: "",
      marks: [],
      models: [],
      generations: [],
      trims: [],
      body: [],
      fuel: [],
      trans: [],
      color: [],
      price_from: "",
      price_to: "",
      mileage_from: "",
      mileage_to: "",
      year_from: "",
      year_to: "",
      drive_awd: false,
      sort: "date_new",
      page: 1,
    });
  };

  const title =
    state.market === "china" ? "Автомобили из Китая" : "Автомобили из Кореи";

  const pages =
    search.meta.pages > 0
      ? search.meta.pages
      : Math.max(1, Math.ceil(search.meta.total / PER_PAGE));

  const activeChips = useMemo(() => {
    const chips: Array<{ key: keyof CatalogUrlState; label: string; value?: string }> = [];
    state.marks.forEach((v) => chips.push({ key: "marks", label: `Марка: ${v}`, value: v }));
    state.models.forEach((v) => chips.push({ key: "models", label: `Модель: ${v}`, value: v }));
    state.generations.forEach((v) =>
      chips.push({ key: "generations", label: `Поколение: ${v}`, value: v }),
    );
    state.trims.forEach((v) => chips.push({ key: "trims", label: `Комплектация: ${v}`, value: v }));
    state.body.forEach((v) => chips.push({ key: "body", label: `Кузов: ${v}`, value: v }));
    state.fuel.forEach((v) => chips.push({ key: "fuel", label: `Топливо: ${v}`, value: v }));
    state.trans.forEach((v) => chips.push({ key: "trans", label: `КПП: ${v}`, value: v }));
    state.color.forEach((v) => chips.push({ key: "color", label: `Цвет: ${v}`, value: v }));
    if (state.drive_awd) chips.push({ key: "drive_awd", label: "Полный привод" });
    if (state.price_from) chips.push({ key: "price_from", label: `Цена от: ${state.price_from}` });
    if (state.price_to) chips.push({ key: "price_to", label: `Цена до: ${state.price_to}` });
    if (state.mileage_from) chips.push({ key: "mileage_from", label: `Пробег от: ${state.mileage_from}` });
    if (state.mileage_to) chips.push({ key: "mileage_to", label: `Пробег до: ${state.mileage_to}` });
    if (state.year_from) chips.push({ key: "year_from", label: `Год от: ${state.year_from}` });
    if (state.year_to) chips.push({ key: "year_to", label: `Год до: ${state.year_to}` });
    return chips;
  }, [state]);

  const removeChip = (chip: { key: keyof CatalogUrlState; value?: string }) => {
    if (
      chip.key === "marks" ||
      chip.key === "models" ||
      chip.key === "generations" ||
      chip.key === "trims" ||
      chip.key === "body" ||
      chip.key === "fuel" ||
      chip.key === "trans" ||
      chip.key === "color"
    ) {
      if (!chip.value) return;
      toggle(chip.key, chip.value);
      return;
    }
    if (chip.key === "drive_awd") {
      navigate({ ...state, drive_awd: false, page: 1 });
      return;
    }
    navigate({ ...state, [chip.key]: "", page: 1 });
  };

  return (
    <div className="mx-auto max-w-[1600px] px-3 pb-10 pt-4 sm:px-4 lg:px-6">
      {err ? (
        <div className="mb-4 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {err} — проверьте{" "}
          <code className="rounded bg-background/80 px-1">NEXT_PUBLIC_API_BASE</code> и доступность API.
        </div>
      ) : null}

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
        <aside className="w-full shrink-0 lg:sticky lg:top-24 lg:w-80 lg:max-h-[calc(100dvh-6.5rem)] lg:overflow-y-auto lg:pe-1">
          <div className="space-y-4 rounded-2xl border border-border bg-card p-4 shadow-sm">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Поиск</label>
              <div className="mt-2 flex gap-2">
                <Input
                  value={qDraft}
                  onChange={(e) => setQDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      navigate({ ...state, q: qDraft.trim(), page: 1 });
                    }
                  }}
                  placeholder="Марка, модель…"
                  className="min-w-0 flex-1"
                />
                <Button
                  type="button"
                  size="sm"
                  className="shrink-0"
                  onClick={() => navigate({ ...state, q: qDraft.trim(), page: 1 })}
                >
                  Найти
                </Button>
              </div>
            </div>

            <div className="border-t border-border pt-4">
              <label className="text-xs font-medium text-muted-foreground">Сортировка</label>
              <select
                value={state.sort}
                onChange={(e) => navigate({ ...state, sort: e.target.value, page: 1 })}
                className="mt-2 flex h-9 w-full rounded-3xl border border-transparent bg-input/50 px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30"
              >
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="border-t border-border pt-4">
              <h2 className="text-sm font-semibold">Цена, пробег, год</h2>
              <div className="mt-3">
                <RangeBlock state={state} navigate={navigate} />
              </div>
              <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={state.drive_awd}
                  onChange={(e) => navigate({ ...state, drive_awd: e.target.checked, page: 1 })}
                  className="size-3.5 rounded border-border accent-primary"
                />
                Полный привод (AWD)
              </label>
            </div>

            {facets ? (
              <div className="space-y-3 border-t border-border pt-4">
                <FacetGroup
                  title="Марка"
                  rows={facets.marks}
                  selected={new Set(state.marks)}
                  onToggle={(v) => toggle("marks", v)}
                />
                <FacetGroup
                  title="Модель"
                  rows={facets.models}
                  selected={new Set(state.models)}
                  onToggle={(v) => toggle("models", v)}
                />
                <FacetGroup
                  title="Поколение"
                  rows={facets.generations}
                  selected={new Set(state.generations)}
                  onToggle={(v) => toggle("generations", v)}
                />
                <FacetGroup
                  title="Комплектация"
                  rows={facets.trims}
                  selected={new Set(state.trims)}
                  onToggle={(v) => toggle("trims", v)}
                />
                <FacetGroup
                  title="Кузов"
                  rows={facets.bodies}
                  selected={new Set(state.body)}
                  onToggle={(v) => toggle("body", v)}
                />
                <FacetGroup
                  title="Топливо"
                  rows={facets.fuels}
                  selected={new Set(state.fuel)}
                  onToggle={(v) => toggle("fuel", v)}
                />
                <FacetGroup
                  title="КПП"
                  rows={facets.transmissions}
                  selected={new Set(state.trans)}
                  onToggle={(v) => toggle("trans", v)}
                />
                <FacetGroup
                  title="Цвет"
                  rows={facets.colors}
                  selected={new Set(state.color)}
                  onToggle={(v) => toggle("color", v)}
                />
              </div>
            ) : (
              <div className="space-y-3 border-t border-border pt-4">
                <FacetSkeleton />
                <FacetSkeleton />
                <FacetSkeleton />
              </div>
            )}

            <Button type="button" variant="outline" className="w-full" onClick={reset}>
              Сбросить фильтры
            </Button>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <div className="mb-5 border-b border-border pb-5">
            <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Найдено:{" "}
              <span className="font-medium text-foreground">
                {search.meta.total.toLocaleString("ru-RU")}
              </span>
              {search.meta.processing_time_ms != null ? ` · ${search.meta.processing_time_ms} ms` : ""}
              {loading ? " · обновление…" : ""}
            </p>
            {activeChips.length ? (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {activeChips.map((chip, idx) => (
                  <Button
                    key={`${chip.key}-${chip.value ?? idx}`}
                    type="button"
                    variant="secondary"
                    size="xs"
                    className="h-7 rounded-full px-2.5 text-xs font-normal"
                    onClick={() => removeChip(chip)}
                    title="Убрать фильтр"
                  >
                    {chip.label} ×
                  </Button>
                ))}
                <Button type="button" size="xs" className="h-7 rounded-full px-3" onClick={reset}>
                  Сбросить все
                </Button>
              </div>
            ) : null}
          </div>

          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {search.result.map((car, idx) => {
              const img = firstImageUrl(car);
              const meta = metaText(car);
              return (
                <li key={car.id}>
                  <Link
                    href={`/car/${encodeURIComponent(car.id)}`}
                    prefetch
                    className="block overflow-hidden rounded-2xl border border-border bg-card shadow-sm transition-shadow hover:shadow-md"
                  >
                    <div className="relative aspect-[16/10] bg-muted">
                      {img ? (
                        <Image
                          src={img}
                          alt=""
                          width={640}
                          height={400}
                          sizes="(min-width: 1280px) 26vw, (min-width: 640px) 44vw, 94vw"
                          className="h-full w-full object-cover"
                          loading={idx < 3 ? "eager" : undefined}
                          fetchPriority={idx === 0 ? "high" : "auto"}
                          decoding="async"
                          unoptimized
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                          Нет фото
                        </div>
                      )}
                      <div className="absolute bottom-2 start-2 rounded-md bg-foreground/85 px-2 py-0.5 text-xs font-medium text-background">
                        {car.year_num ? `${car.year_num}` : "Год не указан"}
                      </div>
                    </div>
                    <div className="space-y-2 p-4">
                      <p className="line-clamp-2 min-h-[2.75rem] text-sm font-medium leading-snug">
                        {car.title || car.id}
                      </p>
                      <p className="line-clamp-1 text-xs text-muted-foreground">{meta || car.id}</p>
                      <p className="text-xl font-semibold">{formatPrice(car.price)}</p>
                    </div>
                  </Link>
                </li>
              );
            })}
            {loading && search.result.length === 0
              ? Array.from({ length: PER_PAGE }).map((_, i) => <CardSkeleton key={`sk-${i}`} />)
              : null}
          </ul>

          {search.result.length === 0 && !loading ? (
            <p className="mt-16 text-center text-muted-foreground">Ничего не найдено по текущим фильтрам.</p>
          ) : null}

          <nav className="mt-10 flex flex-wrap items-center justify-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="rounded-full"
              disabled={state.page <= 1}
              onClick={() => navigate({ ...state, page: state.page - 1 })}
            >
              Назад
            </Button>
            <span className="px-2 text-sm text-muted-foreground">
              Стр. {state.page} из {pages}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="rounded-full"
              disabled={!search.meta.next_cursor}
              onClick={() => navigate({ ...state, page: state.page + 1 })}
            >
              Вперёд
            </Button>
          </nav>
        </div>
      </div>
    </div>
  );
}
