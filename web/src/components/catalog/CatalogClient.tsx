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

function parseJsonMaybe(v: unknown): unknown {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
}

function firstImageUrl(car: SlimCar): string | undefined {
  const candidates: unknown[] = [
    car.data?.image,
    car.data?.img,
    car.data?.photo,
    car.data?.images,
    car.data?.h_images,
  ];

  for (const raw of candidates) {
    const value = parseJsonMaybe(raw);
    if (typeof value === "string" && /^https?:\/\//i.test(value)) return value;
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (typeof item === "string" && /^https?:\/\//i.test(item)) return item;
      if (!item || typeof item !== "object") continue;
      const maybeUrl =
        (item as { url?: unknown; imageUrl?: unknown; src?: unknown }).url ??
        (item as { url?: unknown; imageUrl?: unknown; src?: unknown }).imageUrl ??
        (item as { url?: unknown; imageUrl?: unknown; src?: unknown }).src;
      if (typeof maybeUrl === "string" && /^https?:\/\//i.test(maybeUrl)) return maybeUrl;
    }
  }
  return undefined;
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
    <fieldset className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
      <legend className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {title}
      </legend>
      <div className="max-h-44 space-y-1 overflow-y-auto pr-1 text-sm">
        {rows.map((r) => (
          <label
            key={r.value}
            className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5"
          >
            <input
              type="checkbox"
              checked={selected.has(r.value)}
              onChange={() => onToggle(r.value)}
              className="rounded border-zinc-300"
            />
            <span className="min-w-0 flex-1 truncate" title={r.value}>
              {r.value}
            </span>
            <span className="shrink-0 text-xs tabular-nums text-zinc-400">
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
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
      <div className="mb-2 h-4 w-24  rounded bg-zinc-200" />
      <div className="space-y-2">
        <div className="h-4 w-full  rounded bg-zinc-200" />
        <div className="h-4 w-5/6  rounded bg-zinc-200" />
        <div className="h-4 w-4/6  rounded bg-zinc-200" />
      </div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <li className="overflow-hidden rounded-xl border border-zinc-200 bg-white ">
      <div className="aspect-[16/10]  bg-zinc-200" />
      <div className="space-y-2 p-4">
        <div className="h-4 w-11/12  rounded bg-zinc-200" />
        <div className="h-3 w-1/2  rounded bg-zinc-200" />
        <div className="h-5 w-1/3  rounded bg-zinc-200" />
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
        <input
          placeholder="Цена от"
          value={draft.price_from}
          onChange={(e) => setDraft((d) => ({ ...d, price_from: e.target.value }))}
          className="rounded border border-zinc-300 px-2 py-1.5"
        />
        <input
          placeholder="Цена до"
          value={draft.price_to}
          onChange={(e) => setDraft((d) => ({ ...d, price_to: e.target.value }))}
          className="rounded border border-zinc-300 px-2 py-1.5"
        />
        <input
          placeholder="Пробег от"
          value={draft.mileage_from}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_from: e.target.value }))}
          className="rounded border border-zinc-300 px-2 py-1.5"
        />
        <input
          placeholder="Пробег до"
          value={draft.mileage_to}
          onChange={(e) => setDraft((d) => ({ ...d, mileage_to: e.target.value }))}
          className="rounded border border-zinc-300 px-2 py-1.5"
        />
        <input
          placeholder="Год от"
          value={draft.year_from}
          onChange={(e) => setDraft((d) => ({ ...d, year_from: e.target.value }))}
          className="rounded border border-zinc-300 px-2 py-1.5"
        />
        <input
          placeholder="Год до"
          value={draft.year_to}
          onChange={(e) => setDraft((d) => ({ ...d, year_to: e.target.value }))}
          className="rounded border border-zinc-300 px-2 py-1.5"
        />
      </div>
      <button
        type="button"
        onClick={apply}
        className="mt-2 w-full rounded-lg bg-zinc-800 py-2 text-sm font-medium text-white"
      >
        Применить диапазоны
      </button>
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

  const switchMarket = (market: CatalogUrlState["market"]) => {
    navigate({
      market,
      q: state.q,
      sort: state.sort,
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
      page: 1,
    });
  };

  const title =
    state.market === "china" ? "Автомобили из Китая" : "Автомобили из Кореи";

  const pages =
    search.meta.pages > 0
      ? search.meta.pages
      : Math.max(1, Math.ceil(search.meta.total / PER_PAGE));

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6 flex flex-col gap-4 border-b border-zinc-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Найдено:{" "}
            <span className="font-medium text-zinc-900">
              {search.meta.total.toLocaleString("ru-RU")}
            </span>
            {search.meta.processing_time_ms != null
              ? ` · ${search.meta.processing_time_ms} ms`
              : ""}
            {loading ? " · обновление…" : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => switchMarket("korea")}
            className={`rounded-full px-4 py-2 text-sm font-medium ${
              state.market === "korea"
                ? "bg-zinc-900 text-white"
                : "border border-zinc-300 bg-white text-zinc-800"
            }`}
          >
            Корея
          </button>
          <button
            type="button"
            onClick={() => switchMarket("china")}
            className={`rounded-full px-4 py-2 text-sm font-medium ${
              state.market === "china"
                ? "bg-zinc-900 text-white"
                : "border border-zinc-300 bg-white text-zinc-800"
            }`}
          >
            Китай
          </button>
        </div>
      </div>

      {err ? (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {err} — проверьте{" "}
          <code className="rounded bg-white/60 px-1">NEXT_PUBLIC_API_BASE</code> и
          доступность API.
        </div>
      ) : null}

      <div className="flex flex-col gap-8 lg:flex-row">
        <aside className="w-full shrink-0 space-y-3 lg:w-72">
          <div className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-4">
            <label className="text-xs  font-medium text-zinc-500">Поиск</label>
            <div className="flex gap-2">
              <input
                value={qDraft}
                onChange={(e) => setQDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    navigate({ ...state, q: qDraft.trim(), page: 1 });
                  }
                }}
                placeholder="Марка, модель…"
                className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm"
              />
              <button
                type="button"
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white "
                onClick={() => navigate({ ...state, q: qDraft.trim(), page: 1 })}
              >
                Найти
              </button>
            </div>
            <label className="mt-2 text-xs font-medium text-zinc-500">Сортировка</label>
            <select
              value={state.sort}
              onChange={(e) => navigate({ ...state, sort: e.target.value, page: 1 })}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-3 rounded-xl border border-zinc-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-zinc-800">Диапазоны</h2>
            <RangeBlock
              state={state}
              navigate={navigate}
            />
            <label className="mt-1 flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={state.drive_awd}
                onChange={(e) =>
                  navigate({ ...state, drive_awd: e.target.checked, page: 1 })
                }
              />
              Полный привод (AWD)
            </label>
          </div>

          {facets ? (
            <div className="space-y-3">
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
            <div className="space-y-3">
              <FacetSkeleton />
              <FacetSkeleton />
              <FacetSkeleton />
            </div>
          )}

          <button
            type="button"
            onClick={reset}
            className="w-full rounded-lg border border-zinc-300 py-2 text-sm font-medium text-zinc-800"
          >
            Сбросить фильтры
          </button>
        </aside>

        <div className="min-w-0 flex-1">
          <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {search.result.map((car, idx) => {
              const img = firstImageUrl(car);
              return (
                <li key={car.id}>
                  <Link
                    href={`/car/${encodeURIComponent(car.id)}`}
                    prefetch
                    className="block overflow-hidden rounded-xl border border-zinc-200 bg-white"
                  >
                    <div className="aspect-[16/10] bg-zinc-100">
                      {img ? (
                        <Image
                          src={img}
                          alt=""
                          width={640}
                          height={400}
                          sizes="(min-width: 1280px) 28vw, (min-width: 640px) 45vw, 94vw"
                          className="h-full w-full object-cover"
                          loading={idx < 3 ? "eager" : undefined}
                          fetchPriority={idx === 0 ? "high" : "auto"}
                          decoding="async"
                          unoptimized
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-sm text-zinc-400">
                          Нет фото
                        </div>
                      )}
                    </div>
                    <div className="space-y-1 p-4">
                      <p className="line-clamp-2 min-h-[2.75rem] text-sm font-medium leading-snug text-zinc-900">
                        {car.title || car.id}
                      </p>
                      <p className="text-xs text-zinc-500">
                        {car.year_num ? `${car.year_num} · ` : ""}
                        {car.id}
                      </p>
                      <p className="text-lg font-semibold text-zinc-900">
                        {formatPrice(car.price)}
                      </p>
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
            <p className="mt-16 text-center text-zinc-500">Ничего не найдено по текущим фильтрам.</p>
          ) : null}

          <nav className="mt-10 flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              disabled={state.page <= 1}
              onClick={() => navigate({ ...state, page: state.page - 1 })}
              className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium disabled:opacity-40"
            >
              Назад
            </button>
            <span className="text-sm text-zinc-600">
              Стр. {state.page} из {pages}
            </span>
            <button
              type="button"
              disabled={!search.meta.next_cursor}
              onClick={() => navigate({ ...state, page: state.page + 1 })}
              className="rounded-full border border-zinc-300 px-4 py-2 text-sm font-medium disabled:opacity-40"
            >
              Вперёд
            </button>
          </nav>
        </div>
      </div>
    </div>
  );
}
