"use client";

import Image from "next/image";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import {
  asStr,
  diagnosisStatusTone,
  flatScalarRows,
  buildNormalizedCarTitle,
  formatCarHistoryObjectRow,
  formatHumanDate,
  formatInspectionListItem,
  formatKm,
  formatKrw,
  formatRegYearMonth,
  getPath,
  joinUniqueSpecs,
  prettifyDataKey,
  toneClass,
  translateKoToRuText,
} from "@/lib/car-detail-data";
import { displayEncarStandardOption, localizeEncarOptionText } from "@/lib/encar-options-display";

function localizeLabel(label: string): string {
  return translateKoToRuText(prettifyDataKey(label));
}

function localizeValue(value: string): string {
  const t = translateKoToRuText(value);
  if (t === "[]") return "Не выявлены";
  if (t === "{}") return "Нет данных";
  return t;
}

function SpecGrid({ rows }: { rows: { label: string; value: string }[] }) {
  const filtered = rows.filter((r) => r.value.trim());
  if (!filtered.length) {
    return <p className="text-sm text-muted-foreground">Нет данных.</p>;
  }
  return (
    <dl className="grid grid-cols-1 gap-2.5 md:grid-cols-2 md:gap-3">
      {filtered.map((r) => (
        <div
          key={r.label}
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

function StatusBadge({ title }: { title: string }) {
  const tone = diagnosisStatusTone(title);
  return (
    <Badge variant="outline" className={`mt-0.5 rounded-lg text-xs font-medium ${toneClass(tone)}`}>
      {translateKoToRuText(title)}
    </Badge>
  );
}

function InnerInspectionTree({ nodes, depth }: { nodes: unknown[]; depth: number }) {
  if (!nodes.length) return null;
  return (
    <ul className={depth === 0 ? "space-y-2" : "ms-3 mt-2 space-y-2 border-s border-border/50 ps-3"}>
      {nodes.map((node, idx) => {
        if (!node || typeof node !== "object") return null;
        const o = node as Record<string, unknown>;
        const typeT = asStr(getPath(o, ["type", "title"])) ?? asStr(o.title);
        const statusT = asStr(getPath(o, ["statusType", "title"]));
        const desc = asStr(o.description);
        const diagnosisBlock = o.diagnosis;
        const children = o.children;

        return (
          <li key={idx} className="rounded-lg bg-background/60 py-1">
            <div className="flex flex-wrap items-start gap-2">
              {typeT ? <span className="text-sm font-medium">{translateKoToRuText(typeT)}</span> : null}
              {statusT ? <StatusBadge title={statusT} /> : null}
            </div>
            {desc ? (
              <p className="mt-1 text-xs text-muted-foreground [overflow-wrap:anywhere]">{translateKoToRuText(desc)}</p>
            ) : null}
            {diagnosisBlock && typeof diagnosisBlock === "object" ? (
              <div className="mt-2 rounded-lg border border-border/40 bg-muted/15 p-2 text-xs">
                <SpecGrid
                  rows={flatScalarRows(diagnosisBlock).map(([k, v]) => ({
                    label: prettifyDataKey(k),
                    value: translateKoToRuText(v),
                  }))}
                />
              </div>
            ) : null}
            {Array.isArray(children) && children.length > 0 ? (
              <InnerInspectionTree nodes={children as unknown[]} depth={depth + 1} />
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

function JsonLight({ label, data }: { label: string; data: unknown }) {
  if (data == null) return null;
  let text: string;
  try {
    text = JSON.stringify(data, null, 2);
  } catch {
    text = String(data);
  }
  if (!text || text === "{}") return null;
  return (
    <details className="text-xs">
      <summary className="cursor-pointer font-medium text-muted-foreground">{label}</summary>
      <pre className="mt-2 max-h-48 overflow-auto rounded-md bg-background/90 p-2">{text}</pre>
    </details>
  );
}

function OutersBlock({ outers }: { outers: unknown }) {
  if (!outers || !Array.isArray(outers) || outers.length === 0) {
    return <p className="text-sm text-muted-foreground">Нет данных по внешним панелям.</p>;
  }
  return (
    <ul className="space-y-2">
      {outers.map((item, i) => {
        if (!item || typeof item !== "object") return null;
        const o = item as Record<string, unknown>;
        const rows = flatScalarRows(o).map(([k, v]) => ({ label: k, value: v }));
        return (
          <li key={i} className="rounded-xl border border-border/50 bg-muted/15 p-3">
            <SpecGrid rows={rows} />
          </li>
        );
      })}
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

function krwOrStr(v: unknown): string | null {
  if (v == null || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(/\s/g, ""));
  if (Number.isFinite(n)) return formatKrw(n);
  return asStr(v);
}

function RecordOpenSection({ ro }: { ro: Record<string, unknown> }) {
  const rows: { label: string; value: string }[] = [];
  const add = (label: string, v: unknown, fmt?: (x: unknown) => string | null) => {
    const s = fmt ? fmt(v) : asStr(v);
    if (s) rows.push({ label, value: s });
  };

  add("ДТП (всего)", ro.accidentCnt);
  add("Мои ДТП", ro.myAccidentCnt);
  add("Чужие ДТП", ro.otherAccidentCnt);
  add("Ущерб (мои)", ro.myAccidentCost, krwOrStr);
  add("Ущерб (прочие)", ro.otherAccidentCost, krwOrStr);
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
  const carInfoChanges = ro.carInfoChanges;
  const usageChangeTypes = ro.usageChangeTypes;

  return (
    <div className="space-y-4">
      <SpecGrid rows={rows} />
      {Array.isArray(accidents) && accidents.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Страховые случаи
          </h4>
          <ul className="space-y-2">
            {accidents.map((a, i) => (
              <li key={i} className="rounded-lg border border-border/40 bg-muted/10 p-2 text-xs">
                <pre className="whitespace-pre-wrap [overflow-wrap:anywhere]">
                  {JSON.stringify(a, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {Array.isArray(ownerChanges) && ownerChanges.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Смена собственников
          </h4>
          <ul className="space-y-2 text-sm">
            {ownerChanges.map((oc, i) => (
              <li key={i} className="rounded-lg border border-border/40 bg-muted/10 px-3 py-2 [overflow-wrap:anywhere]">
                {formatHumanDate(oc) ?? asStr(oc) ?? JSON.stringify(oc)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {Array.isArray(carInfoChanges) && carInfoChanges.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Смена госномеров / данные авто
          </h4>
          <ul className="space-y-2 text-sm">
            {carInfoChanges.map((c, i) => (
              <li
                key={i}
                className="rounded-lg border border-border/40 bg-muted/10 px-3 py-2 [overflow-wrap:anywhere]"
              >
                {formatCarHistoryObjectRow(c)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {usageChangeTypes != null && String(usageChangeTypes).length > 0 ? (
        <JsonLight label="Изменения использования (usageChangeTypes)" data={usageChangeTypes} />
      ) : null}
    </div>
  );
}

function EquipmentSection({ d, extra }: { d: Record<string, unknown>; extra: Record<string, unknown> | undefined }) {
  const options = d.options as Record<string, unknown> | undefined;
  const standard = options?.standard;
  const codes = Array.isArray(standard) ? standard : [];

  const sp = getPath(extra, ["sellingpoint"]) as Record<string, unknown> | undefined;
  const uniquePhotos = getPath(sp, ["uniqueOptionPhotos"]);
  const choicePhotos = getPath(sp, ["choiceOptionPhotos"]);
  const sellingPoint = getPath(sp, ["sellingPoint"]) as Record<string, unknown> | undefined;
  const advMasters = getPath(sp, ["advertisementMasters"]);

  return (
    <div className="space-y-5">
      {codes.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Опции</h4>
          <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {codes.map((c, i) => (
              <li
                key={i}
                className="rounded-xl border border-border/45 bg-muted/10 px-3 py-2 text-xs leading-snug transition-colors hover:bg-muted/20"
              >
                {displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Стандартные опции не указаны.</p>
      )}

      {Array.isArray(uniquePhotos) && uniquePhotos.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Уникальные опции</h4>
          <ul className="space-y-2">
            {uniquePhotos.map((item, i) => {
              if (!item || typeof item !== "object") return null;
              const o = item as Record<string, unknown>;
              const rawName = asStr(o.partName) ?? asStr(o.name) ?? "";
              const name = localizeEncarOptionText(rawName);
              if (!name) return null;
              return (
                <li key={i} className="rounded-lg border border-border/50 px-2 py-1.5 text-sm">
                  {name}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {Array.isArray(choicePhotos) && choicePhotos.length > 0 ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Выбранные опции с фото</h4>
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {choicePhotos.map((item, i) => {
              if (!item || typeof item !== "object") return null;
              const o = item as Record<string, unknown>;
              const name =
                localizeEncarOptionText(asStr(o.partName) ?? asStr(o.name) ?? "") ?? "Опция";
              const url =
                asStr(o.photoUrl) ?? asStr(o.imageUrl) ?? asStr(o.url) ?? asStr(o.imgUrl);
              return (
                <li key={i} className="overflow-hidden rounded-xl border border-border/60 bg-card">
                  {url ? (
                    <div className="relative aspect-[4/3] bg-muted">
                      <Image src={url} alt="" fill className="object-cover" sizes="200px" unoptimized />
                    </div>
                  ) : null}
                  <p className="p-2 text-xs font-medium">{name}</p>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {sellingPoint && (asStr(sellingPoint.sentence) || asStr(sellingPoint.photoUrl as unknown)) ? (
        <div className="rounded-xl border border-border/50 bg-muted/15 p-3">
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Акцент продажи</h4>
          {asStr(sellingPoint.sentence) ? (
            <p className="text-sm [overflow-wrap:anywhere]">{translateKoToRuText(asStr(sellingPoint.sentence)!)}</p>
          ) : null}
          {asStr(sellingPoint.photoUrl) ? (
            <div className="relative mt-2 aspect-video max-w-md overflow-hidden rounded-lg bg-muted">
              <Image
                src={asStr(sellingPoint.photoUrl)!}
                alt=""
                fill
                className="object-cover"
                sizes="400px"
                unoptimized
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {advMasters != null && (Array.isArray(advMasters) ? advMasters.length > 0 : true) ? (
        <div>
          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Рекламные блоки (advertisementMasters)</h4>
          <JsonLight label="advertisementMasters" data={advMasters} />
        </div>
      ) : null}
    </div>
  );
}

export function CarDetailAccordions({
  data,
  diagnosisPhotosCount,
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

  const carStateTitle = asStr(getPath(detail, ["carStateType", "title"]));
  const inspComments = asStr(detail?.comments);

  const inners = inspection?.inners;
  const innerList = Array.isArray(inners) ? inners : [];

  const recordOpen =
    extra?.record_open && typeof extra.record_open === "object"
      ? (extra.record_open as Record<string, unknown>)
      : undefined;

  const inspName = asStr(detail?.inspName);
  const recordNo = asStr(detail?.recordNo);
  const validityStart = asStr(detail?.validityStartDate);
  const validityEnd = asStr(detail?.validityEndDate);
  const guarantyTitle = asStr(getPath(detail, ["guarantyType", "title"]));
  const firstReg = asStr(detail?.firstRegistrationDate);
  const carNo = asStr(detail?.carNo);
  const fuel = asStr(detail?.fuel);
  const carShape = asStr(detail?.carShape);

  const defaultOpen = ["general"];

  const dongchediHighlightsRaw = parseJson(data.dongchedi_specs_highlights);
  const dongchediHighlightRows: { label: string; value: string }[] = [];
  if (Array.isArray(dongchediHighlightsRaw)) {
    for (const item of dongchediHighlightsRaw) {
      if (!item || typeof item !== "object") continue;
      const o = item as { label?: unknown; value?: unknown };
      const lb = typeof o.label === "string" ? o.label : "";
      const vl = typeof o.value === "string" ? o.value : o.value != null ? String(o.value) : "";
      if (lb && vl) dongchediHighlightRows.push({ label: lb, value: vl });
    }
  }

  const hasStructuredSub =
    !!(engineTransmission && Object.keys(engineTransmission).length > 0) ||
    !!(chassis && Object.keys(chassis).length > 0) ||
    !!(electrical && Object.keys(electrical).length > 0) ||
    !!(additional && Object.keys(additional).length > 0);

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
              <OutersBlock outers={outers} />
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

            {bodyChanged != null && (typeof bodyChanged !== "object" || Object.keys(bodyChanged as object).length > 0) ? (
              <div>
                <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Замены кузовных деталей</h4>
                {typeof bodyChanged === "object" && !Array.isArray(bodyChanged) ? (
                  <SpecGrid
                    rows={Object.entries(bodyChanged as Record<string, unknown>).map(([k, v]) => ({
                      label: k,
                      value: asStr(v) ?? JSON.stringify(v),
                    }))}
                  />
                ) : (
                  <p className="text-sm [overflow-wrap:anywhere]">{JSON.stringify(bodyChanged)}</p>
                )}
              </div>
            ) : null}
          </div>
        </AccordionContent>
      </AccordionItem>

      <AccordionItem value="diagnosis">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Диагностика и техсостояние
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <div className="space-y-5">
            {diagnosisPhotosCount > 0 ? (
              <p className="text-xs text-muted-foreground">
                В галерее выше: {diagnosisPhotosCount} фото диагностики / днища.
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">Фото диагностики отсутствуют.</p>
            )}

            {carStateTitle ? (
              <div>
                <span className="text-xs font-semibold text-muted-foreground">Общий вердикт</span>
                <p className="mt-1 text-sm font-medium">{translateKoToRuText(carStateTitle)}</p>
              </div>
            ) : null}
            {inspComments ? (
              <div>
                <span className="text-xs font-semibold text-muted-foreground">Комментарии инспекции</span>
                <p className="mt-1 whitespace-pre-wrap text-sm [overflow-wrap:anywhere]">
                  {translateKoToRuText(inspComments)}
                </p>
              </div>
            ) : null}

            {hasStructuredSub ? (
              <Accordion
                type="multiple"
                className="rounded-2xl border border-border/55 bg-muted/10"
                defaultValue={[]}
              >
                {engineTransmission && Object.keys(engineTransmission).length > 0 ? (
                  <AccordionItem value="de-et">
                    <AccordionTrigger className="px-4 text-sm [overflow-wrap:anywhere]">
                      Двигатель и трансмиссия
                    </AccordionTrigger>
                    <AccordionContent>
                      <SpecGrid
                        rows={Object.entries(engineTransmission).map(([k, v]) => ({
                          label: prettifyDataKey(k),
                          value: asStr(v)
                            ? translateKoToRuText(asStr(v)!)
                            : typeof v === "object"
                              ? translateKoToRuText(JSON.stringify(v))
                              : "—",
                        }))}
                      />
                    </AccordionContent>
                  </AccordionItem>
                ) : null}
                {chassis && Object.keys(chassis).length > 0 ? (
                  <AccordionItem value="de-ch">
                    <AccordionTrigger className="px-4 text-sm [overflow-wrap:anywhere]">Ходовая и тормоза</AccordionTrigger>
                    <AccordionContent>
                      <SpecGrid
                        rows={Object.entries(chassis).map(([k, v]) => ({
                          label: prettifyDataKey(k),
                          value: asStr(v)
                            ? translateKoToRuText(asStr(v)!)
                            : typeof v === "object"
                              ? translateKoToRuText(JSON.stringify(v))
                              : "—",
                        }))}
                      />
                    </AccordionContent>
                  </AccordionItem>
                ) : null}
                {electrical && Object.keys(electrical).length > 0 ? (
                  <AccordionItem value="de-el">
                    <AccordionTrigger className="px-4 text-sm [overflow-wrap:anywhere]">Электрика</AccordionTrigger>
                    <AccordionContent>
                      <SpecGrid
                        rows={Object.entries(electrical).map(([k, v]) => ({
                          label: prettifyDataKey(k),
                          value: asStr(v)
                            ? translateKoToRuText(asStr(v)!)
                            : typeof v === "object"
                              ? translateKoToRuText(JSON.stringify(v))
                              : "—",
                        }))}
                      />
                    </AccordionContent>
                  </AccordionItem>
                ) : null}
                {additional && Object.keys(additional).length > 0 ? (
                  <AccordionItem value="de-ad">
                    <AccordionTrigger className="px-4 text-sm [overflow-wrap:anywhere]">
                      Дополнительные проверки
                    </AccordionTrigger>
                    <AccordionContent>
                      <SpecGrid
                        rows={Object.entries(additional).map(([k, v]) => ({
                          label: prettifyDataKey(k),
                          value: asStr(v)
                            ? translateKoToRuText(asStr(v)!)
                            : typeof v === "object"
                              ? translateKoToRuText(JSON.stringify(v))
                              : "—",
                        }))}
                      />
                    </AccordionContent>
                  </AccordionItem>
                ) : null}
              </Accordion>
            ) : (
              <p className="text-sm text-muted-foreground">Структурированные блоки диагностики отсутствуют.</p>
            )}

            {innerList.length > 0 ? (
              <div>
                <h4 className="mb-2 text-xs font-semibold text-muted-foreground">Детальная диагностика (inners)</h4>
                <InnerInspectionTree nodes={innerList} depth={0} />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Вложенная диагностика inners отсутствует.</p>
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

      <AccordionItem value="extra" className="last:rounded-b-3xl">
        <AccordionTrigger className="break-words py-4 ps-4 pe-10 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:bg-muted/30 hover:no-underline sm:ps-5 sm:pe-12">
          Дополнительные сведения
        </AccordionTrigger>
        <AccordionContent className="px-4 sm:px-5">
          <div className="space-y-4">
            {dongchediHighlightRows.length > 0 ? (
              <div>
                <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
                  Параметры модели (Dongchedi)
                </h4>
                <SpecGrid rows={dongchediHighlightRows} />
              </div>
            ) : null}
            <SpecGrid
              rows={[
                { label: "Станция инспекции", value: translateKoToRuText(inspName ?? "") },
                { label: "Номер записи", value: recordNo ?? "" },
                {
                  label: "Срок гарантии",
                  value: [formatHumanDate(validityStart) ?? validityStart, formatHumanDate(validityEnd) ?? validityEnd]
                    .filter(Boolean)
                    .join(" — "),
                },
                { label: "Тип гарантии", value: translateKoToRuText(guarantyTitle ?? "") },
                { label: "Первая регистрация", value: formatHumanDate(firstReg) ?? firstReg ?? "" },
                { label: "Номер кузова", value: carNo ?? "" },
                { label: "Топливо", value: translateKoToRuText(fuel ?? "") },
                { label: "Форма кузова", value: translateKoToRuText(carShape ?? "") },
              ]}
            />
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}
