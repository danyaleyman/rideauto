import type { ReactNode } from "react";
import { pickCarData } from "@/lib/car-seo";
import { formatPriceLabel } from "@/lib/format-price";

const LABELS: Record<string, string> = {
  mark: "Марка",
  model: "Модель",
  generation: "Поколение",
  configuration: "Комплектация",
  gradeName: "Комплектация (grade)",
  year: "Год",
  yearMonth: "Год и месяц",
  km_age: "Пробег, км",
  color: "Цвет кузова",
  interior_color: "Цвет салона",
  engine_type: "Двигатель / топливо",
  transmission_type: "КПП",
  drive_type: "Привод",
  prep_drive_type: "Привод (API)",
  body_type: "Тип кузова",
  displacement: "Объём (см³ / литраж)",
  dongchedi_displacement_label: "Объём (как в объявлении)",
  power: "Мощность, л.с.",
  hp: "Мощность, л.с.",
  vin: "VIN",
  vehicle_no: "Номер кузова",
  inner_id: "ID источника",
  url: "Ссылка на источник",
  my_price: "Цена (расчёт), ₽",
  price: "Цена (сырой номер)",
  price_won: "Цена, вон",
  price_cny: "Цена, CNY",
  address: "Адрес / регион",
  city: "Город",
  seller_type: "Тип продавца",
  is_dealer: "Дилер",
  offer_created: "Дата объявления",
  created_at: "Создано в БД",
  source: "Источник",
  description: "Описание",
  dongchedi_sku_id: "Dongchedi SKU",
  dongchedi_series_name: "Серия (КНР)",
  dongchedi_summary: "Краткое описание (КНР)",
  dongchedi_msrp_rub: "MSRP нового, ₽",
  dongchedi_msrp_cny: "MSRP нового, CNY",
  dongchedi_market_time: "Выход на рынок (модель)",
  transfer_count: "Число перепродаж",
  seatCount: "Мест",
  advertisementType: "Тип объявления",
  salesStatus: "Статус продаж",
  power_source: "Источник данных о мощности",
  power_estimated: "Мощность оценена",
  insurance_cases: "Страховые случаи",
  insurance_payout_krw: "Выплаты, KRW",
  insurance_payout_rub: "Выплаты, ₽",
  damaged_parts_count: "Повреждённых элементов",
  status: "Статус",
  offer_status: "Статус лота",
  engine_displacement_cc: "Объём двигателя, см³",
};

const SKIP_SCALAR: Set<string> = new Set([
  "images",
  "h_images",
  "extra",
  "options",
  "complectation",
  "id",
  "is_duplicate",
  "is_awd",
  "dongchedi_specs_highlights",
]);

function humanize(k: string): string {
  if (LABELS[k]) return LABELS[k];
  if (k.startsWith("dongchedi_")) return k.replace(/^dongchedi_/, "КНР: ").replace(/_/g, " ");
  return k.replace(/_/g, " ");
}

function asString(v: unknown): string | null {
  if (v == null || v === "") return null;
  if (typeof v === "boolean") return v ? "Да" : "Нет";
  if (typeof v === "number" && Number.isFinite(v)) return String(v);
  if (typeof v === "string") {
    const s = v.trim();
    return s || null;
  }
  return null;
}

function formatScalar(key: string, v: unknown): string | null {
  if (typeof v === "number" && Number.isFinite(v)) {
    const kl = key.toLowerCase();
    if (
      kl === "my_price" ||
      kl.includes("msrp_rub") ||
      (kl.includes("rub") && !kl.includes("cny")) ||
      (kl.includes("payout") && kl.includes("rub"))
    ) {
      return formatPriceLabel(v);
    }
    if (kl.includes("cny")) return `${v.toLocaleString("ru-RU")} CNY`;
    if (kl.includes("won") || kl.includes("krw")) return `${v.toLocaleString("ru-RU")} ₩`;
    return String(v);
  }
  return asString(v);
}

function objectEntriesRows(obj: unknown): [string, string][] {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
    const s = formatScalar(k, v);
    if (s) out.push([humanize(k) || k, s]);
  }
  return out;
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-6 rounded-2xl border border-border bg-card p-5 shadow-sm ring-1 ring-border/40">
      <h2 className="font-heading text-lg font-semibold tracking-tight">{title}</h2>
      {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      {children}
    </section>
  );
}

function KeyTable({ rows }: { rows: [string, string][] }) {
  if (!rows.length) return <p className="mt-3 text-sm text-muted-foreground">Нет данных.</p>;
  return (
    <dl className="mt-4 divide-y divide-border/60">
      {rows.map(([k, v], i) => (
        <div
          key={`${k}-${i}`}
          className="grid gap-1 py-2.5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] sm:gap-4"
        >
          <dt className="text-sm text-muted-foreground">{k}</dt>
          <dd className="text-sm font-medium [overflow-wrap:anywhere]">{v}</dd>
        </div>
      ))}
    </dl>
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

function OptionsBlock({ options }: { options: unknown }) {
  const o = options as Record<string, unknown> | null;
  if (!o || typeof o !== "object") return null;
  const std = o.standard;
  const arr = Array.isArray(std) ? std : [];
  if (!arr.length) return null;
  const lines = arr.map((x) => (typeof x === "string" ? x : JSON.stringify(x)));
  return (
    <Section title="Опции и комплектация (штатное оборудование)" description="Как в объявлении источника">
      <ul className="mt-4 list-inside list-disc space-y-1 text-sm [overflow-wrap:anywhere]">
        {lines.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </Section>
  );
}

function JsonDetails({ name, data }: { name: string; data: unknown }) {
  if (data == null) return null;
  let text: string;
  try {
    text = JSON.stringify(data, null, 2);
  } catch {
    text = String(data);
  }
  if (!text || text === "{}" || text === "[]") return null;
  return (
    <details className="mt-4 rounded-xl border border-border/60 bg-muted/20 p-3">
      <summary className="cursor-pointer text-sm font-medium">{name}</summary>
      <pre className="mt-3 max-h-[420px] overflow-auto rounded-lg bg-background/80 p-3 text-xs leading-relaxed">{text}</pre>
    </details>
  );
}

function DongchediHighlights(d: Record<string, unknown>) {
  const raw = d.dongchedi_specs_highlights;
  const parsed = parseJson(raw);
  if (!Array.isArray(parsed) || !parsed.length) return null;
  const rows: [string, string][] = [];
  for (const item of parsed) {
    if (!item || typeof item !== "object") continue;
    const o = item as { label?: unknown; value?: unknown };
    const lb = typeof o.label === "string" ? o.label : "";
    const vl = typeof o.value === "string" ? o.value : o.value != null ? String(o.value) : "";
    if (lb && vl) rows.push([lb, vl]);
  }
  if (!rows.length) return null;
  return (
    <Section
      title="Параметры модели (Dongchedi)"
      description="Сводка со страницы комплектации, если собиралась парсером"
    >
      <KeyTable rows={rows} />
    </Section>
  );
}

function StructuredInspection(structured: Record<string, unknown> | undefined) {
  if (!structured || typeof structured !== "object") return null;

  const basic = structured.basicInfo as Record<string, unknown> | undefined;
  const bodyChanged = structured.bodyChanged as Record<string, unknown> | undefined;
  const interior = structured.interior as Record<string, unknown> | undefined;
  const bodyPanels = structured.bodyPanels as unknown;
  const engineTransmission = structured.engineTransmission as Record<string, unknown> | undefined;
  const chassis = structured.chassis as Record<string, unknown> | undefined;
  const electrical = structured.electrical as Record<string, unknown> | undefined;
  const additional = structured.additional as Record<string, unknown> | undefined;
  const bodyComments = structured.bodyComments;

  const hasAny =
    (basic && Object.keys(basic).length > 0) ||
    (bodyChanged && Object.keys(bodyChanged).length > 0) ||
    (interior && Object.keys(interior).length > 0) ||
    (Array.isArray(bodyPanels) && bodyPanels.length > 0) ||
    (engineTransmission && Object.keys(engineTransmission).length > 0) ||
    (chassis && Object.keys(chassis).length > 0) ||
    (electrical && Object.keys(electrical).length > 0) ||
    (additional && Object.keys(additional).length > 0) ||
    (typeof bodyComments === "string" && bodyComments.trim());

  if (!hasAny) return null;

  return (
    <Section
      title="Осмотр и диагностика (Encar)"
      description="Сводка из inspection + diagnosis API: кузов, техника, комментарии"
    >
      {basic && Object.keys(basic).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Общие сведения осмотра</h3>
          <KeyTable rows={objectEntriesRows(basic)} />
        </>
      ) : null}

      {bodyChanged && Object.keys(bodyChanged).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Кузов: замены, окрас, ремонт</h3>
          <KeyTable
            rows={Object.entries(bodyChanged).map(([k, v]) => [
              k,
              typeof v === "string" ? v : String(v),
            ])}
          />
        </>
      ) : null}

      {interior && Object.keys(interior).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Салон / внутренние элементы</h3>
          <KeyTable
            rows={Object.entries(interior).map(([k, v]) => [
              k,
              typeof v === "string" ? v : String(v),
            ])}
          />
        </>
      ) : null}

      {Array.isArray(bodyPanels) && bodyPanels.length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Панели кузова (программа диагностики)</h3>
          <KeyTable
            rows={bodyPanels.map((p: unknown) => {
              if (!p || typeof p !== "object") return ["—", ""];
              const o = p as { part?: unknown; status?: unknown };
              const part = typeof o.part === "string" ? o.part : "—";
              const st = typeof o.status === "string" ? o.status : o.status != null ? String(o.status) : "";
              return [part, st];
            })}
          />
        </>
      ) : null}

      {engineTransmission && Object.keys(engineTransmission).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Двигатель и трансмиссия</h3>
          <KeyTable rows={objectEntriesRows(engineTransmission)} />
        </>
      ) : null}

      {chassis && Object.keys(chassis).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Шасси, подвеска, рулевое, тормоза</h3>
          <KeyTable rows={objectEntriesRows(chassis)} />
        </>
      ) : null}

      {electrical && Object.keys(electrical).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Электрооборудование</h3>
          <KeyTable rows={objectEntriesRows(electrical)} />
        </>
      ) : null}

      {additional && Object.keys(additional).length > 0 ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Дополнительно</h3>
          <KeyTable rows={objectEntriesRows(additional)} />
        </>
      ) : null}

      {typeof bodyComments === "string" && bodyComments.trim() ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">Комментарии к кузову и осмотру</h3>
          <p className="mt-2 whitespace-pre-wrap rounded-xl border border-border/50 bg-muted/30 p-3 text-sm [overflow-wrap:anywhere]">
            {bodyComments.trim()}
          </p>
        </>
      ) : null}
    </Section>
  );
}

function GeneralScalars(d: Record<string, unknown>) {
  const rows: [string, string][] = [];
  for (const [k, v] of Object.entries(d)) {
    if (SKIP_SCALAR.has(k)) continue;
    if (k === "description") continue;
    if (v == null || v === "") continue;
    if (typeof v === "object") continue;
    const s = formatScalar(k, v);
    if (!s) continue;
    rows.push([humanize(k), s]);
  }
  rows.sort((a, b) => a[0].localeCompare(b[0], "ru"));
  return <KeyTable rows={rows} />;
}

function DescriptionBlock(text: unknown) {
  if (typeof text !== "string" || !text.trim()) return null;
  return (
    <Section title="Текст объявления">
      <p className="mt-3 whitespace-pre-wrap text-sm [overflow-wrap:anywhere]">{text.trim()}</p>
    </Section>
  );
}

function ExtraTechnical(extra: Record<string, unknown>) {
  const diagPhotos = extra.diagnosis_photos;
  const nDiag = Array.isArray(diagPhotos) ? diagPhotos.length : 0;
  const structured =
    extra.inspection_structured && typeof extra.inspection_structured === "object"
      ? (extra.inspection_structured as Record<string, unknown>)
      : undefined;

  return (
    <>
      {nDiag > 0 ? (
        <Section title="Фото диагностики" description={`В галерее выше добавлено ${nDiag} снимков днища / диагностики.`}>
          <p className="mt-2 text-sm text-muted-foreground">
            Источник: Encar underbody / DIAG2 — см. полный список URL в техническом блоке ниже при необходимости.
          </p>
        </Section>
      ) : null}
      <StructuredInspection structured={structured} />
      <JsonDetails name="Сырой ответ diagnosis (API)" data={extra.diagnosis} />
      <JsonDetails name="Сырой ответ inspection (API)" data={extra.inspection} />
      <JsonDetails name="Форматы осмотра (inspection_formats)" data={extra.inspection_formats} />
      <JsonDetails name="inspection_structured (полный JSON)" data={extra.inspection_structured} />
      <JsonDetails name="sellingpoint" data={extra.sellingpoint} />
      <JsonDetails name="record_open (открытые данные)" data={extra.record_open} />
    </>
  );
}

export function CarDetailSections({ raw }: { raw: Record<string, unknown> }) {
  const d = pickCarData(raw);
  const extra =
    d.extra && typeof d.extra === "object" && !Array.isArray(d.extra)
      ? (d.extra as Record<string, unknown>)
      : undefined;

  return (
    <>
      <Section
        title="Общие данные"
        description="Все сохранённые скалярные поля карточки (кроме массивов фото и тяжёлых вложений)"
      >
        <GeneralScalars d={d} />
      </Section>

      <OptionsBlock options={d.options} />

      <DongchediHighlights d={d} />

      {DescriptionBlock(d.description)}

      {extra ? <ExtraTechnical extra={extra} /> : null}

      <JsonDetails name="Полный блок data (JSON)" data={d} />
    </>
  );
}
