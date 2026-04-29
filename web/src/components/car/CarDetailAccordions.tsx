"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import {
  asStr,
  cleanScalarText,
  diagnosisStatusTone,
  flatScalarRows,
  buildNormalizedCarTitle,
  formatHumanDate,
  formatInspectionListItem,
  formatKm,
  formatKrw,
  formatRubFromUnknown,
  formatRegYearMonth,
  getPath,
  joinUniqueSpecs,
  prettifyDataKey,
  toneClass,
  translateKoToRuText,
} from "@/lib/car-detail-data";
import {
  collectSelectedEncarOptions,
  displayEncarStandardOption,
} from "@/lib/encar-options-display";
import { localizeDongchediOptionText } from "@/lib/dongchedi-option-ru-table";
import { formatPriceLabel } from "@/lib/format-price";

function localizeLabel(label: string): string {
  return translateKoToRuText(prettifyDataKey(label));
}

function localizeValue(value: string): string {
  const cleaned = cleanScalarText(value);
  if (!cleaned) return "Не указано";
  const t = translateKoToRuText(cleaned);
  if (t === "[]") return "Не выявлены";
  if (t === "{}") return "Нет данных";
  return t;
}

function SpecGrid({ rows }: { rows: { label: string; value: string }[] }) {
  const filtered = rows
    .map((r) => ({ label: r.label, value: cleanScalarText(r.value) ?? "" }))
    .filter((r) => r.value.trim());
  if (!filtered.length) {
    return <p className="text-sm text-muted-foreground">Нет данных.</p>;
  }
  return (
    <dl className="grid grid-cols-1 gap-2.5 md:grid-cols-2 md:gap-3">
      {filtered.map((r, idx) => (
        <div
          key={`${r.label}-${idx}`}
          className="rounded-2xl border border-border/45 bg-muted/15 px-3 py-2.5 transition-colors hover:bg-muted/25 md:grid md:grid-cols-[minmax(0,42%)_minmax(0,1fr)] md:gap-3 md:px-3.5 md:py-3"
        >
          <dt className="text-[11px] font-semibold tracking-wide text-muted-foreground md:pt-0.5">
            {localizeLabel(r.label)}
          </dt>
          <dd className="mt-1 text-sm font-medium leading-snug [overflow-wrap:anywhere] text-foreground md:mt-0">
            {localizeValue(r.value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function bodyStatusColor(text: string): string {
  const t = text.toLowerCase();
  if (t.includes("ориг") || t.includes("정상") || t.includes("양호")) return "bg-emerald-100 text-emerald-900 border-emerald-300";
  if (t.includes("окрас") || t.includes("판금") || t.includes("도장")) return "bg-amber-100 text-amber-900 border-amber-300";
  if (t.includes("замен") || t.includes("교환")) return "bg-red-100 text-red-900 border-red-300";
  if (t.includes("ремонт") || t.includes("수리")) return "bg-orange-100 text-orange-900 border-orange-300";
  return "bg-slate-100 text-slate-800 border-slate-300";
}

function BodyStateChips({
  outers,
  bodyChanged,
}: {
  outers: unknown;
  bodyChanged: unknown;
}) {
  const rows: Array<{ part: string; status: string }> = [];
  if (Array.isArray(outers)) {
    for (const item of outers) {
      if (!item || typeof item !== "object") continue;
      const o = item as Record<string, unknown>;
      const part = translateKoToRuText(asStr(o.partName) ?? asStr(o.part) ?? asStr(o.name) ?? "");
      const status = translateKoToRuText(
        asStr(getPath(o, ["statusType", "title"])) ?? asStr(o.status) ?? asStr(o.result) ?? "Оригинал",
      );
      if (part && status) rows.push({ part, status });
    }
  }
  if (bodyChanged && typeof bodyChanged === "object" && !Array.isArray(bodyChanged)) {
    for (const [k, v] of Object.entries(bodyChanged as Record<string, unknown>)) {
      const part = translateKoToRuText(k);
      const status = translateKoToRuText(asStr(v) ?? "Замена");
      if (part && status) rows.push({ part, status });
    }
  }
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">Повреждений не зафиксировано, элементы кузова в исходном состоянии.</p>;
  }
  return (
    <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
      {rows.map((r, i) => (
        <li key={`${r.part}-${i}`} className="flex items-center justify-between gap-2 rounded-xl border border-border/50 px-3 py-2">
          <span className="text-sm">{r.part}</span>
          <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${bodyStatusColor(r.status)}`}>{r.status}</span>
        </li>
      ))}
    </ul>
  );
}

function parseJson(v: unknown): unknown {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v) as unknown;
  } catch {
    return null;
  }
}

function collectDongchediRecommendedFallback(d: Record<string, unknown>): string[] {
  const raw = d.high_light_config;
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const item = entry as Record<string, unknown>;
    const candidate = asStr(item.name) ?? asStr(item.title) ?? asStr(item.value);
    if (!candidate) continue;
    const ru = localizeDongchediOptionText(candidate);
    if (!ru || seen.has(ru)) continue;
    seen.add(ru);
    out.push(ru);
  }
  return out;
}

function formatInsuranceType(v: unknown): string | null {
  const s = cleanScalarText(v);
  if (!s) return null;
  if (s === "1") return "Случай по моему авто";
  if (s === "2") return "Случай по чужому авто";
  return s;
}

function AccidentCases({ items }: { items: unknown[] }) {
  const list = items
    .map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : null))
    .filter((x): x is Record<string, unknown> => Boolean(x))
    .filter((x) => String(x.type ?? "").trim() !== "2");
  if (!list.length) return null;
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Страховые случаи по этому авто
      </h4>
      <ul className="space-y-2.5">
        {list.map((a, i) => {
          const date = formatHumanDate(a.date) ?? cleanScalarText(a.date);
          const partCost = Number(a.partCost ?? 0);
          const laborCost = Number(a.laborCost ?? 0);
          const paintCost = Number(a.paintingCost ?? 0);
          const hasBodyWork = Number.isFinite(partCost + laborCost + paintCost) && partCost + laborCost + paintCost > 0;
          const kind = hasBodyWork ? "Кузовной/ремонтный случай" : "Технический/гарантийный случай";
          const part = formatRubFromUnknown(a.partCost) ?? formatKrw(Number(a.partCost ?? 0));
          const labor = formatRubFromUnknown(a.laborCost) ?? formatKrw(Number(a.laborCost ?? 0));
          const paint = formatRubFromUnknown(a.paintingCost) ?? formatKrw(Number(a.paintingCost ?? 0));
          const payout = formatRubFromUnknown(a.insuranceBenefit) ?? formatKrw(Number(a.insuranceBenefit ?? 0));
          return (
            <li key={i} className="rounded-xl border border-border/50 bg-muted/15 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {date ? <Badge variant="secondary">{date}</Badge> : null}
                <Badge variant="outline">{kind}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p><span className="text-muted-foreground">Запчасти:</span> {part}</p>
                <p><span className="text-muted-foreground">Работы:</span> {labor}</p>
                <p><span className="text-muted-foreground">Покраска:</span> {paint}</p>
                <p><span className="text-muted-foreground">Страховая выплата:</span> {payout}</p>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">
        Показываются только случаи, относящиеся к текущему автомобилю. Данные по второму участнику скрыты.
      </p>
    </div>
  );
}

function RecordOpenSection({ ro }: { ro: Record<string, unknown> }) {
  const [krwRate, setKrwRate] = useState<number | null>(null);
  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const r = await fetch(`/api/cbr-rates?ts=${Date.now()}`, { cache: "no-store" });
        if (!r.ok) return;
        const d = (await r.json()) as { valute?: Record<string, { Value: number; Nominal: number }> };
        const val = d?.valute?.KRW;
        if (!val || !Number.isFinite(val.Value) || !Number.isFinite(val.Nominal) || val.Nominal <= 0) return;
        const rate = val.Value / val.Nominal;
        if (!cancelled) setKrwRate(rate);
      } catch {
        // ignore
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  const num = (v: unknown): number | null => {
    if (v == null || v === "") return null;
    const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, ""));
    return Number.isFinite(n) ? n : null;
  };
  const rubFromKrw = (v: unknown): string | null => {
    const n = num(v);
    if (n == null) return null;
    if (krwRate == null) return `${Math.round(n).toLocaleString("ru-RU")} ₩`;
    return formatPriceLabel(n * krwRate);
  };

  const rows: { label: string; value: string }[] = [];
  const add = (label: string, v: unknown, fmt?: (x: unknown) => string | null) => {
    const s = fmt ? fmt(v) : asStr(v);
    if (s) rows.push({ label, value: s });
  };

  add("ДТП по авто", ro.myAccidentCnt);
  add("Ущерб (мои)", ro.myAccidentCost, rubFromKrw);
  add("Полная гибель (кол-во)", ro.totalLossCnt);
  add("Дата полной гибели", ro.totalLossDate, (v) => formatHumanDate(v) ?? asStr(v));
  add("Затопление: тотал", ro.floodTotalLossCnt);
  add("Затопление: частичное", ro.floodPartLossCnt);
  add("Дата затопления", ro.floodDate, (v) => formatHumanDate(v) ?? asStr(v));
  add("Угон (кол-во)", ro.robberCnt);
  add("Дата угона", ro.robberDate, (v) => formatHumanDate(v) ?? asStr(v));
  add("Период без страховки 1", ro.notJoinDate1, (v) => formatHumanDate(v) ?? asStr(v));
  add("Период без страховки 2", ro.notJoinDate2, (v) => formatHumanDate(v) ?? asStr(v));
  add("Период без страховки 3", ro.notJoinDate3, (v) => formatHumanDate(v) ?? asStr(v));
  add("Отзывные кампании", ro.recall);
  add("Отзывные (детализация)", ro.recallFullFillTypes);

  const accidents = ro.accidents;
  const ownerChanges = ro.ownerChanges;
  const ownersCount = Array.isArray(ownerChanges) ? ownerChanges.length : Number(ro.ownerChangeCnt ?? 0);
  const ownerChipClass =
    ownersCount > 5
      ? "text-red-700 border-red-300 bg-red-50"
      : "text-emerald-700 border-emerald-300 bg-emerald-50";

  return (
    <div className="space-y-4">
      <SpecGrid rows={rows} />
      {Array.isArray(accidents) && accidents.length > 0 ? <AccidentCases items={accidents} /> : null}
      {ownersCount > 0 ? (
        <Badge variant="outline" className={`rounded-full text-xs ${ownerChipClass}`}>
          Собственников авто в Корее: {ownersCount}
        </Badge>
      ) : null}
    </div>
  );
}

function EquipmentSection({ d, extra }: { d: Record<string, unknown>; extra: Record<string, unknown> | undefined }) {
  const source = (asStr(d.source) || "").toLowerCase();
  const isDongchedi = source === "dongchedi" || source === "china";
  const options = d.options as Record<string, unknown> | undefined;
  const standard = options?.standard;
  const codes = useMemo(() => (Array.isArray(standard) ? standard : []), [standard]);
  const dongchediRecommendedRaw = parseJson(d.dongchedi_recommended_options);
  const dongchediRecommendedFallback = useMemo(() => collectDongchediRecommendedFallback(d), [d]);
  const dongchediRecommended = useMemo(() => {
    if (!Array.isArray(dongchediRecommendedRaw)) return dongchediRecommendedFallback;
    const out: string[] = [];
    const seen = new Set<string>();
    for (const item of dongchediRecommendedRaw) {
      const ru = localizeDongchediOptionText(typeof item === "string" ? item : item != null ? String(item) : "");
      if (!ru || seen.has(ru)) continue;
      seen.add(ru);
      out.push(ru);
    }
    return out.length ? out : dongchediRecommendedFallback;
  }, [dongchediRecommendedRaw, dongchediRecommendedFallback]);

  const sp = getPath(extra, ["sellingpoint"]) as Record<string, unknown> | undefined;
  const uniquePhotos = getPath(sp, ["uniqueOptionPhotos"]);
  const choicePhotos = getPath(sp, ["choiceOptionPhotos"]);
  const selectedOptions = useMemo(
    () => collectSelectedEncarOptions(uniquePhotos, choicePhotos, extra, d),
    [uniquePhotos, choicePhotos, extra, d],
  );
  const selectedCodes = useMemo(
    () => new Set(selectedOptions.map((x) => (x.code || "").trim()).filter(Boolean)),
    [selectedOptions],
  );
  const selectedLabels = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const row of selectedOptions) {
      const lb = cleanScalarText(row.label);
      if (!lb || /^Опция\s+\d+$/i.test(lb) || seen.has(lb)) continue;
      seen.add(lb);
      out.push(lb);
    }
    for (const c of codes) {
      const label = cleanScalarText(displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d));
      if (!label || /^Опция\s+\d+$/i.test(label) || seen.has(label)) continue;
      seen.add(label);
      out.push(label);
    }
    return out;
  }, [selectedOptions, codes, uniquePhotos, choicePhotos, extra, d]);
  const staticCodesFiltered = codes.filter((c) => {
    const s = cleanScalarText(c);
    if (!s) return false;
    if (!selectedCodes.size) return true;
    return selectedCodes.has(s);
  });
  const hasAnyRenderedOptions = dongchediRecommended.length > 0 || selectedLabels.length > 0;

  return (
    <div className="space-y-5">
      {isDongchedi && dongchediRecommended.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Опции конкретного авто ({selectedLabels.length})</h4>
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {dongchediRecommended.map((label, i) => (
              <li
                key={i}
                className="rounded-xl border border-border/55 bg-background px-3 py-2 text-xs leading-snug"
              >
                {label}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {selectedLabels.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Опции конкретного авто</h4>
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {selectedLabels.map((label, i) => (
              <li
                key={i}
                className="rounded-xl border border-border/55 bg-background px-3 py-2 text-xs leading-snug"
              >
                {label}
              </li>
            ))}
          </ul>
        </div>
      ) : !hasAnyRenderedOptions ? (
        <p className="text-sm text-muted-foreground">По этой карточке опции не распознаны.</p>
      ) : null}

      {staticCodesFiltered.length > 0 && !hasAnyRenderedOptions ? (
        <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {staticCodesFiltered.map((c, i) => (
            <li key={i} className="rounded-xl border border-border/55 bg-background px-3 py-2 text-xs leading-snug">
              {displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function CarDetailAccordions({
  data,
  diagnosisPhotosCount: _diagnosisPhotosCount,
}: {
  data: Record<string, unknown>;
  diagnosisPhotosCount: number;
}) {
  const extra =
    data.extra && typeof data.extra === "object" && !Array.isArray(data.extra)
      ? (data.extra as Record<string, unknown>)
      : undefined;

  const inspection = getPath(extra, ["inspection"]) as Record<string, unknown> | undefined;
  const master = inspection?.master as Record<string, unknown> | undefined;
  const detail = getPath(master, ["detail"]) as Record<string, unknown> | undefined;

  const mileage =
    formatKm(data.km_age) ??
    formatKm(getPath(detail, ["mileage"])) ??
    formatKm(getPath(extra, ["inspection", "master", "detail", "mileage"]));

  const vin = asStr(data.vin) ?? asStr(getPath(detail, ["vin"]));

  const power =
    asStr((data as Record<string, unknown>).power_kwhp) ??
    asStr(data.power) ??
    asStr(data.hp);

  const generalRows: { label: string; value: string }[] = [];
  const push = (label: string, v: string | null) => {
    if (v) generalRows.push({ label, value: v });
  };

  push(
    "Наименование",
    buildNormalizedCarTitle(
      data.mark,
      data.model,
      data.generation ?? data.configuration ?? data.gradeName,
      data.source,
    ) ??
      joinUniqueSpecs(data.mark, data.model, data.generation),
  );
  push("Год / месяц", formatRegYearMonth(data.yearMonth) ?? formatRegYearMonth(data.year));
  push("Цвет", asStr(data.color));
  push("Пробег", mileage);
  push("VIN", vin);
  push(
    "Двигатель / объём",
    [asStr(data.engine_type), asStr(data.displacement)].filter(Boolean).join(", ") || null,
  );
  push("КПП / привод", [asStr(data.transmission_type), asStr(data.drive_type)].filter(Boolean).join(", ") || null);
  push("Мощность", power);
  push("Места", asStr(data.seatCount));

  const paintPartTypes = detail?.paintPartTypes ?? getPath(detail, ["paintPartTypes"]);
  const seriousTypes = detail?.seriousTypes ?? getPath(detail, ["seriousTypes"]);
  const boardTitle = asStr(getPath(detail, ["boardStateType", "title"]));

  const outers = inspection?.outers;

  const accident = master?.accdient ?? master?.accident;
  const simpleRepair = master?.simpleRepair;
  const bodyChanged =
    getPath(extra, ["inspection_structured", "bodyChanged"]) ?? getPath(master, ["bodyChanged"]);

  const structured =
    extra?.inspection_structured && typeof extra.inspection_structured === "object"
      ? (extra.inspection_structured as Record<string, unknown>)
      : undefined;

  const engineTransmission = structured?.engineTransmission as Record<string, unknown> | undefined;
  const chassis = structured?.chassis as Record<string, unknown> | undefined;
  const electrical = structured?.electrical as Record<string, unknown> | undefined;
  const additional = structured?.additional as Record<string, unknown> | undefined;

  const recordOpen =
    extra?.record_open && typeof extra.record_open === "object"
      ? (extra.record_open as Record<string, unknown>)
      : undefined;

  const defaultOpen = ["general"];

  const toStructuredRows = (obj: Record<string, unknown> | undefined): Array<{ label: string; value: string }> => {
    if (!obj) return [];
    return Object.entries(obj)
      .map(([k, v]) => {
        const base = asStr(v)
          ? translateKoToRuText(asStr(v)!)
          : typeof v === "object"
            ? translateKoToRuText(JSON.stringify(v))
            : "";
        const cleaned = cleanScalarText(base);
        return cleaned ? { label: translateKoToRuText(prettifyDataKey(k)), value: translateKoToRuText(cleaned) } : null;
      })
      .filter((x): x is { label: string; value: string } => Boolean(x));
  };

  const diagSections = [
    { key: "engine", label: "Двигатель", rows: toStructuredRows(engineTransmission) },
    { key: "chassis", label: "Ходовая и тормоза", rows: toStructuredRows(chassis) },
    { key: "electrical", label: "Электрика", rows: toStructuredRows(electrical) },
    { key: "additional", label: "Дополнительно", rows: toStructuredRows(additional) },
  ].filter((x) => x.rows.length > 0);
  const [activeDiagTab, setActiveDiagTab] = useState<string>(diagSections[0]?.key ?? "engine");
  const activeDiag = diagSections.find((x) => x.key === activeDiagTab) ?? diagSections[0];
  useEffect(() => {
    if (!diagSections.length) return;
    if (!diagSections.some((x) => x.key === activeDiagTab)) {
      setActiveDiagTab(diagSections[0].key);
    }
  }, [diagSections, activeDiagTab]);

  return (
    <Accordion
      type="multiple"
      defaultValue={defaultOpen}
      className="mt-6 max-w-full overflow-hidden rounded-2xl border border-border/70 bg-card shadow-sm ring-1 ring-black/[0.04] dark:ring-white/[0.07] sm:rounded-3xl"
    >
      <AccordionItem value="general" className="first:rounded-t-3xl">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Общая информация
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <SpecGrid rows={generalRows} />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="equipment">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Комплектация
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <EquipmentSection d={data} extra={extra} />
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="body">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Состояние кузова
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <div className="space-y-4">
            {paintPartTypes != null ? (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Окрашенные детали</h4>
                {Array.isArray(paintPartTypes) && paintPartTypes.length > 0 ? (
                  <ul className="list-inside list-disc text-sm">
                    {paintPartTypes.map((x, i) => (
                      <li key={i} className="[overflow-wrap:anywhere]">
                        {translateKoToRuText(typeof x === "object" ? formatInspectionListItem(x) : String(x))}
                      </li>
                    ))}
                  </ul>
                ) : typeof paintPartTypes === "object" ? (
                  <SpecGrid rows={flatScalarRows(paintPartTypes).map(([k, v]) => ({ label: k, value: v }))} />
                ) : (
                  <p className="text-sm">{translateKoToRuText(asStr(paintPartTypes) ?? "Не выявлены")}</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Нет данных по окрашенным деталям.</p>
            )}
            {seriousTypes != null ? (
              <div>
                <h4 className="mb-1 text-xs font-semibold text-muted-foreground">Серьёзные повреждения</h4>
                {Array.isArray(seriousTypes) && seriousTypes.length > 0 ? (
                  <ul className="list-inside list-disc text-sm">
                    {seriousTypes.map((x, i) => (
                      <li key={i} className="[overflow-wrap:anywhere]">
                        {translateKoToRuText(typeof x === "object" ? formatInspectionListItem(x) : String(x))}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm [overflow-wrap:anywhere]">Не выявлены</p>
                )}
              </div>
            ) : null}
            {boardTitle ? (
              <p className="text-sm">
                <span className="text-muted-foreground">Состояние кузова: </span>
                {translateKoToRuText(boardTitle)}
              </p>
            ) : null}

            <div>
              <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Внешние элементы кузова</h4>
              <BodyStateChips outers={outers} bodyChanged={bodyChanged} />
            </div>

            <div className="flex flex-wrap gap-2">
              {accident != null ? (
                <Badge variant="outline" className="rounded-lg">
                  ДТП (данные осмотра): {asStr(accident) ?? JSON.stringify(accident)}
                </Badge>
              ) : null}
              {simpleRepair != null ? (
                <Badge variant="outline" className="rounded-lg">
                  Косметический ремонт: {asStr(simpleRepair) ?? JSON.stringify(simpleRepair)}
                </Badge>
              ) : null}
            </div>

          </div>
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="diagnosis">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Диагностика и техсостояние
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <div className="space-y-5">
            {diagSections.length > 0 ? (
              <div className="space-y-3">
                <div className="inline-flex w-full rounded-xl border border-border/60 bg-muted/20 p-1">
                  {diagSections.map((section) => (
                    <button
                      key={section.key}
                      type="button"
                      onClick={() => setActiveDiagTab(section.key)}
                      className={`flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                        activeDiag?.key === section.key
                          ? "bg-background shadow-sm text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {section.label}
                    </button>
                  ))}
                </div>
                {activeDiag ? (
                  <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {activeDiag.rows.map((row) => (
                      <li key={`${activeDiag.key}-${row.label}`} className="rounded-xl border border-border/50 bg-background px-3 py-2">
                        <p className="text-xs text-muted-foreground">{row.label}</p>
                        <div className="mt-1 flex items-center justify-between gap-2">
                          <p className="text-sm font-medium">{row.value}</p>
                          <Badge variant="outline" className={toneClass(diagnosisStatusTone(row.value))}>
                            {diagnosisStatusTone(row.value) === "ok"
                              ? "Исправно"
                              : diagnosisStatusTone(row.value) === "warn"
                                ? "Требует внимания"
                                : diagnosisStatusTone(row.value) === "bad"
                                  ? "Проблема"
                                  : "Проверить"}
                          </Badge>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Структурированные блоки диагностики отсутствуют.</p>
            )}
          </div>
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="insurance">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Страховые случаи и история
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          {recordOpen && Object.keys(recordOpen).length > 0 ? (
            <RecordOpenSection ro={recordOpen} />
          ) : (
            <p className="text-sm text-muted-foreground">Нет открытых страховых данных (record_open).</p>
          )}
        </AccordionContent>
      </AccordionItem>

    </Accordion>
  );
}
