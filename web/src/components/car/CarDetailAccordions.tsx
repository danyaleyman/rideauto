"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
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
  buildNormalizedCarTitle,
  formatHumanDate,
  formatKm,
  normalizeFuelLabel,
  pickRegYearMonthDisplay,
  getPath,
  joinUniqueSpecs,
  prettifyDataKey,
  translateKoToRuText,
} from "@/lib/car-detail-data";
import {
  collectSelectedEncarOptions,
  displayEncarStandardOption,
} from "@/lib/encar-options-display";
import { classifyAutotraderOptionGroup } from "@/lib/autotrader-options-display";
import { classifyChinaOptionGroup, displayChinaOptionRu, isChinaOptionNoise } from "@/lib/china-options-display";
import { collectAutotraderFeatureLabels } from "@/lib/car-equipment-labels";
import { formatPriceLabel } from "@/lib/format-price";
import {
  bodyStatusColor,
  collectBodyRows,
  hasStructuredBodyPayload,
} from "@/lib/car-body-panels";
import { useLocaleContext } from "@/components/LocaleProvider";
import type { AppLocale, TParams } from "@/lib/i18n";
import { displayColor, displayDriveType, displayTransmission } from "@/lib/vehicle-spec-locale";
import { SegmentedControl, SegmentedControlScroll } from "@/components/ui/segmented-control";

type TI18n = (path: string, params?: TParams) => string;
const CarAccI18nCtx = createContext<{ t: TI18n; locale: AppLocale } | null>(null);

function useCarAccI18n() {
  const ctx = useContext(CarAccI18nCtx);
  if (!ctx) throw new Error("CarAccI18nCtx missing");
  return ctx;
}

function localizeLabel(label: string): string {
  return translateKoToRuText(prettifyDataKey(label));
}

function localizeValue(value: string, tr: TI18n): string {
  const cleaned = cleanScalarText(value);
  if (!cleaned) return tr("car.accordions.notSpecified");
  const t = translateKoToRuText(cleaned);
  if (t === "[]") return tr("car.accordions.notDetected");
  if (t === "{}") return tr("car.accordions.noData");
  return t;
}

function SpecGrid({ rows }: { rows: { label: string; value: string }[] }) {
  const { t } = useCarAccI18n();
  const filtered = rows
    .map((r) => ({ label: r.label, value: cleanScalarText(r.value) ?? "" }))
    .filter((r) => r.value.trim());
  if (!filtered.length) {
    return <p className="text-sm text-muted-foreground">{t("car.accordions.noDataDot")}</p>;
  }
  return (
    <dl className="grid grid-cols-1 gap-x-10 md:grid-cols-2">
      {filtered.map((r, idx) => (
        <div
          key={`${r.label}-${idx}`}
          className="grid grid-cols-[minmax(0,44%)_minmax(0,1fr)] gap-3 border-b border-border/70 py-2.5 text-sm last:border-b-0 md:[&:nth-last-child(2)]:border-b-0"
        >
          <dt className="text-muted-foreground">{localizeLabel(r.label)}</dt>
          <dd className="font-medium leading-snug text-foreground [overflow-wrap:anywhere]">
            {localizeValue(r.value, t)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function isNegativeFlag(v: unknown): boolean {
  const raw = String(v ?? "").trim();
  if (!raw) return true;
  const s = translateKoToRuText(raw).trim().toLowerCase();
  return ["нет", "없음", "no", "normal", "0", "false", "n"].includes(s);
}

function BodyConditionSection({
  outers,
  bodyPanels,
  bodyChanged,
  paintPartTypes,
  seriousTypes,
  diagnosisItems,
  accident,
  simpleRepair: _simpleRepair,
}: {
  outers: unknown;
  bodyPanels: unknown;
  bodyChanged: unknown;
  paintPartTypes: unknown;
  seriousTypes: unknown;
  diagnosisItems: unknown;
  accident: unknown;
  simpleRepair: unknown;
}) {
  void _simpleRepair;
  const { t } = useCarAccI18n();
  const reduceMotion = useReducedMotion();
  const hasStructured = useMemo(
    () =>
      hasStructuredBodyPayload(
        bodyPanels,
        outers,
        bodyChanged,
        paintPartTypes,
        seriousTypes,
        diagnosisItems,
      ),
    [bodyPanels, outers, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems],
  );
  const encarAccident = !isNegativeFlag(accident);

  const groups = useMemo(
    () => collectBodyRows({ outers, bodyPanels, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems }),
    [outers, bodyPanels, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems],
  );

  const tabs = useMemo(
    () =>
      [
        { key: "external" as const, title: t("car.accordions.bodyExternal"), rows: groups.external },
        { key: "internal" as const, title: t("car.accordions.bodyInternal"), rows: groups.internal },
      ] as const,
    [groups.external, groups.internal, t],
  );
  const [activeTab, setActiveTab] = useState<"external" | "internal">("external");
  useEffect(() => {
    if (!tabs.length) return;
    if (!tabs.some((x) => x.key === activeTab)) setActiveTab(tabs[0].key);
  }, [tabs, activeTab]);
  const activeRows = tabs.find((x) => x.key === activeTab)?.rows ?? [];

  if (!hasStructured && !encarAccident) {
    return (
      <p className="text-sm text-muted-foreground">{t("car.accordions.bodyNoInspection")}</p>
    );
  }

  if (!tabs.some((t) => t.rows.length > 0)) {
    return <p className="text-sm text-muted-foreground">{t("car.accordions.bodyNoDamage")}</p>;
  }
  return (
    <div className="space-y-3">
      {encarAccident ? (
        <div className="rounded-lg bg-amber-500/10 px-3 py-2.5 text-xs leading-snug text-amber-950 dark:bg-amber-400/10 dark:text-amber-50">
          <p className="[overflow-wrap:anywhere]">{t("car.accordions.bodyAccidentWarn")}</p>
        </div>
      ) : null}
      <SegmentedControl
        value={activeTab}
        onChange={setActiveTab}
        items={tabs.map((tab) => ({ value: tab.key, label: tab.title }))}
        aria-label={t("car.accordions.bodySectionsAria")}
      />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeTab}
          initial={reduceMotion ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
          transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          {activeRows.length ? (
            <ul className="grid grid-cols-1 gap-x-10 md:grid-cols-2">
              {activeRows.map((r, i) => (
                <li key={`${activeTab}-${r.part}-${i}`} className="flex items-center justify-between gap-3 border-b border-border/70 py-2 text-sm last:border-b-0 md:[&:nth-last-child(2)]:border-b-0">
                  <span>{r.part}</span>
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${bodyStatusColor(r.status)}`}>{r.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              {t("car.accordions.bodySectionClear", {
                section: activeTab === "internal" ? t("car.accordions.bodyInternal") : t("car.accordions.bodyExternal"),
              })}
            </p>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
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

function normalizeSpecValue(v: unknown): string | null {
  const s = asStr(v)?.trim();
  if (!s) return null;
  const low = s.toLowerCase();
  if (["--", "-", "—", "null", "none", "n/a", "undefined", "не указано"].includes(low)) return null;
  return s;
}

function isMeaningfulOptionLabel(v: string): boolean {
  if (isChinaOptionNoise(v)) return false;
  const t = v.trim();
  if (!t) return false;
  if (/^\d+$/.test(t)) return false;
  if (/^[\W_]+$/.test(t)) return false;
  return true;
}

function parseHp(v: unknown): number | null {
  const s = normalizeSpecValue(v);
  if (!s) return null;
  const tagged = /(\d{2,4})\s*(?:hp|ps|л\.?с\.?|horsepower|马力)?/i.exec(s);
  if (tagged) {
    const n = Number(tagged[1]);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  const plain = Number.parseInt(s.replace(/[^\d]/g, ""), 10);
  return Number.isFinite(plain) && plain > 0 ? plain : null;
}

/** Опции/подсветки китайского листинга (Che168 и др.): без отдельной таблицы Dongchedi. */
function collectChinaHighlightLabels(d: Record<string, unknown>): string[] {
  const raw = d.high_light_config;
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const item = entry as Record<string, unknown>;
    const candidate = asStr(item.name) ?? asStr(item.title) ?? asStr(item.value);
    if (!candidate) continue;
    const ru = translateKoToRuText(candidate).trim() || candidate.trim();
    if (!ru || seen.has(ru)) continue;
    seen.add(ru);
    out.push(ru);
  }
  return out;
}

function AccidentCases({
  items,
  title,
  krwRate,
}: {
  items: unknown[];
  title: string;
  krwRate: number;
}) {
  const { t } = useCarAccI18n();
  const list = items
    .map((x) => (x && typeof x === "object" ? (x as Record<string, unknown>) : null))
    .filter((x): x is Record<string, unknown> => Boolean(x));
  if (!list.length) return null;
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <ul className="space-y-2.5">
        {list.map((a, i) => {
          const date = formatHumanDate(a.date) ?? cleanScalarText(a.date);
          const partCost = Number(a.partCost ?? 0);
          const laborCost = Number(a.laborCost ?? 0);
          const paintCost = Number(a.paintingCost ?? 0);
          const hasBodyWork = Number.isFinite(partCost + laborCost + paintCost) && partCost + laborCost + paintCost > 0;
          const kind = hasBodyWork ? t("car.accordions.accidentBody") : t("car.accordions.accidentTech");
          const rubOrNone = (v: unknown): string => {
            const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/\s/g, ""));
            if (!Number.isFinite(n) || n <= 0) return t("car.accordions.none");
            return formatPriceLabel(n * krwRate);
          };
          const part = rubOrNone(a.partCost);
          const labor = rubOrNone(a.laborCost);
          const paint = rubOrNone(a.paintingCost);
          const payout = rubOrNone(a.insuranceBenefit);
          return (
            <li key={i} className="rounded-lg bg-muted/50 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                {date ? <Badge variant="secondary">{date}</Badge> : null}
                <Badge variant="outline">{kind}</Badge>
              </div>
              <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p><span className="text-muted-foreground">{t("car.accordions.parts")}</span> {part}</p>
                <p><span className="text-muted-foreground">{t("car.accordions.labor")}</span> {labor}</p>
                <p><span className="text-muted-foreground">{t("car.accordions.paint")}</span> {paint}</p>
                <p><span className="text-muted-foreground">{t("car.accordions.payout")}</span> {payout}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RecordOpenSection({ ro }: { ro: Record<string, unknown> }) {
  const { t } = useCarAccI18n();
  const reduceMotion = useReducedMotion();
  const [krwRate, setKrwRate] = useState<number | null>(null);
  const krwRubRateSafe = krwRate && Number.isFinite(krwRate) && krwRate > 0 ? krwRate : 0.0539;
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
    return formatPriceLabel(n * krwRubRateSafe);
  };

  const rows: { label: string; value: string }[] = [];
  const add = (label: string, v: unknown, fmt?: (x: unknown) => string | null) => {
    const s = fmt ? fmt(v) : asStr(v);
    if (s) rows.push({ label, value: s });
  };
  const asCount = (v: unknown): number => {
    const n = typeof v === "number" ? v : Number(String(v ?? "").replace(/\s/g, ""));
    return Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : 0;
  };
  const myAccCnt = asCount(ro.myAccidentCnt);
  const totalLossCnt = asCount(ro.totalLossCnt);
  const floodTotalCnt = asCount(ro.floodTotalLossCnt);
  const floodPartCnt = asCount(ro.floodPartLossCnt);
  const theftCnt = asCount(ro.robberCnt);

  add(t("car.accordions.insMyAccidents"), String(myAccCnt));
  add(t("car.accordions.insMyPayout"), ro.myAccidentCost, (v) => {
    const n = asCount(v);
    if (n <= 0) return t("car.accordions.none");
    return rubFromKrw(v);
  });
  add(
    t("car.accordions.insTotalLoss"),
    totalLossCnt > 0 ? t("car.accordions.yesCount", { count: totalLossCnt }) : t("car.accordions.none"),
  );
  add(
    t("car.accordions.insFlood"),
    floodTotalCnt > 0 || floodPartCnt > 0
      ? t("car.accordions.flood", { total: floodTotalCnt, partial: floodPartCnt })
      : t("car.accordions.none"),
  );
  add(
    t("car.accordions.insTheft"),
    theftCnt > 0 ? t("car.accordions.yesTheft", { count: theftCnt }) : t("car.accordions.none"),
  );
  add(t("car.accordions.insRecall"), ro.recall, (v) => {
    const raw = translateKoToRuText(String(v ?? "")).trim();
    if (!raw || raw === "0" || raw.toLowerCase() === "none") return t("car.accordions.none");
    return raw;
  });
  add(t("car.accordions.insRecallStatus"), ro.recallFullFillTypes, (v) => {
    const raw = translateKoToRuText(String(v ?? "")).trim();
    if (!raw || raw === "0" || raw.toLowerCase() === "none") return t("car.accordions.noDataShort");
    return raw;
  });

  const accidents = ro.accidents;
  const ownerChanges = ro.ownerChanges;
  const ownersCount = Array.isArray(ownerChanges) ? ownerChanges.length : Number(ro.ownerChangeCnt ?? 0);
  const mineCases = Array.isArray(accidents)
    ? accidents.filter((x) => x && typeof x === "object" && String((x as Record<string, unknown>).type ?? "").trim() !== "2")
    : [];
  const otherCases = Array.isArray(accidents)
    ? accidents.filter((x) => x && typeof x === "object" && String((x as Record<string, unknown>).type ?? "").trim() === "2")
    : [];
  const hasOtherCases = otherCases.length > 0;
  const [insuranceTab, setInsuranceTab] = useState<"mine" | "other">("mine");
  useEffect(() => {
    if (!hasOtherCases && insuranceTab === "other") setInsuranceTab("mine");
  }, [hasOtherCases, insuranceTab]);

  return (
    <div className="space-y-4">
      <SpecGrid rows={rows} />
      {ownersCount > 0 ? (
        <p className="text-sm">
          <span className="text-muted-foreground">{t("car.accordions.ownersLabel")}: </span>
          <span className="font-medium">{t("car.accordions.ownersCount", { count: ownersCount })}</span>
        </p>
      ) : null}
      {Array.isArray(accidents) && accidents.length > 0 ? (
        <div className="space-y-3">
          {hasOtherCases ? (
            <SegmentedControlScroll
              value={insuranceTab}
              onChange={setInsuranceTab}
              items={[
                { value: "mine", label: t("car.accordions.insTabMine") },
                { value: "other", label: t("car.accordions.insTabOther") },
              ]}
              aria-label={t("car.accordions.insCasesAria")}
            />
          ) : null}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={insuranceTab}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
              transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <AccidentCases
                items={insuranceTab === "other" ? otherCases : mineCases}
                title={
                  insuranceTab === "other"
                    ? t("car.accordions.insCasesOther")
                    : t("car.accordions.insCasesMine")
                }
                krwRate={krwRubRateSafe}
              />
            </motion.div>
          </AnimatePresence>
        </div>
      ) : null}
    </div>
  );
}

function collectListingEquipmentEntries(
  d: Record<string, unknown>,
  extra: Record<string, unknown> | undefined,
): Array<{ label: string; raw: string }> {
  const options = d.options as Record<string, unknown> | undefined;
  const codes = Array.isArray(options?.standard) ? options.standard : [];
  const chinaRecommendedRaw = parseJson(
    d.options_real ?? d.che168_recommended_options ?? d.che168_options_enriched,
  );
  const chinaRecommendedFallback = collectChinaHighlightLabels(d);
  let chinaRecommended: Array<{ label: string; raw: string }> = [];
  if (Array.isArray(chinaRecommendedRaw)) {
    const seen = new Set<string>();
    for (const item of chinaRecommendedRaw) {
      const raw =
        typeof item === "string"
          ? item
          : item && typeof item === "object"
            ? (asStr((item as Record<string, unknown>).name) ??
              asStr((item as Record<string, unknown>).value) ??
              String(item))
            : item != null
              ? String(item)
              : "";
      const ru =
        displayChinaOptionRu(raw) ||
        displayChinaOptionRu(translateKoToRuText(raw)) ||
        translateKoToRuText(raw).trim() ||
        raw.trim();
      if (!isMeaningfulOptionLabel(ru) || seen.has(ru)) continue;
      seen.add(ru);
      chinaRecommended.push({ label: ru, raw });
    }
  }
  if (!chinaRecommended.length) {
    chinaRecommended = chinaRecommendedFallback.map((label) => ({ label, raw: label }));
  }

  const sp = getPath(extra, ["sellingpoint"]) as Record<string, unknown> | undefined;
  const uniquePhotos = getPath(sp, ["uniqueOptionPhotos"]);
  const choicePhotos = getPath(sp, ["choiceOptionPhotos"]);
  const selectedOptions = collectSelectedEncarOptions(uniquePhotos, choicePhotos, extra, d);
  const selectedLabels: string[] = [];
  {
    const seen = new Set<string>();
    for (const row of selectedOptions) {
      const lb = cleanScalarText(row.label);
      if (!lb || /^Опция\s+\d+$/i.test(lb) || seen.has(lb)) continue;
      seen.add(lb);
      selectedLabels.push(lb);
    }
    for (const c of codes) {
      const label = cleanScalarText(displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d));
      if (!label || /^Опция\s+\d+$/i.test(label) || seen.has(label)) continue;
      seen.add(label);
      selectedLabels.push(label);
    }
  }
  const staticCodesAll = codes
    .map((c) => cleanScalarText(displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, d)))
    .filter((x): x is string => Boolean(x));
  const autotraderLabels = collectAutotraderFeatureLabels(d);

  const seen = new Set<string>();
  const out: Array<{ label: string; raw: string }> = [];
  const push = (label: string, raw = label) => {
    const cleaned = cleanScalarText(label);
    if (!cleaned || /^Опция\s+\d+$/i.test(cleaned) || seen.has(cleaned)) return;
    seen.add(cleaned);
    out.push({ label: cleaned, raw });
  };
  for (const row of chinaRecommended) push(row.label, row.raw);
  for (const v of selectedLabels) push(v, v);
  for (const v of staticCodesAll) push(v, v);
  for (const v of autotraderLabels) push(v, v);
  return out;
}

function listingHasEquipment(
  d: Record<string, unknown>,
  extra: Record<string, unknown> | undefined,
): boolean {
  return collectListingEquipmentEntries(d, extra).length > 0;
}

function EquipmentSection({ d, extra }: { d: Record<string, unknown>; extra: Record<string, unknown> | undefined }) {
  const { t } = useCarAccI18n();
  const reduceMotion = useReducedMotion();
  const allLabels = useMemo(() => collectListingEquipmentEntries(d, extra), [d, extra]);
  const hasAnyRenderedOptions = allLabels.length > 0;

  type OptGroupKey = "assist" | "interior" | "safety" | "comfort" | "media" | "other";
  const grouped = useMemo(() => {
    const buckets: Record<OptGroupKey, string[]> = {
      assist: [],
      interior: [],
      safety: [],
      comfort: [],
      media: [],
      other: [],
    };
    for (const { label, raw } of allLabels) {
      // Autotrader labels are already mapped to RU; try AT classifier first, then China/Encar.
      const at = classifyAutotraderOptionGroup(label, raw);
      const key = at !== "other" ? at : classifyChinaOptionGroup(label, raw);
      buckets[key].push(label);
    }
    return buckets;
  }, [allLabels]);
  const groupMeta = useMemo(() => {
    const base: ReadonlyArray<{ key: OptGroupKey; title: string }> = [
      { key: "assist", title: t("car.accordions.equipAssist") },
      { key: "interior", title: t("car.accordions.equipInterior") },
      { key: "safety", title: t("car.accordions.equipSafety") },
      { key: "comfort", title: t("car.accordions.equipComfort") },
      { key: "media", title: t("car.accordions.equipMedia") },
      { key: "other", title: t("car.accordions.equipOther") },
    ];
    return base.filter((g) => grouped[g.key].length > 0);
  }, [grouped, t]);
  const [activeGroup, setActiveGroup] = useState<OptGroupKey>("assist");
  useEffect(() => {
    if (!groupMeta.length) return;
    if (!groupMeta.some((g) => g.key === activeGroup)) setActiveGroup(groupMeta[0].key);
  }, [groupMeta, activeGroup]);
  const activeItems = grouped[activeGroup] ?? [];

  return (
    <div className="space-y-5">
      {!hasAnyRenderedOptions ? (
        <p className="text-sm text-muted-foreground">{t("car.accordions.equipNone")}</p>
      ) : (
        <div className="space-y-3">
          {groupMeta.length > 1 ? (
            <SegmentedControlScroll
              value={activeGroup}
              onChange={setActiveGroup}
              items={groupMeta.map((g) => ({ value: g.key, label: g.title }))}
              aria-label={t("car.accordions.equipGroupsAria")}
            />
          ) : null}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeGroup}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
              transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
              className="overflow-hidden"
            >
              <ul className="grid grid-cols-1 gap-x-8 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
                {activeItems.map((label, i) => (
                  <li key={`${activeGroup}-${i}`} className="flex items-start gap-2 text-sm leading-snug">
                    <Check className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="min-w-0">{label}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}

function normalizeDiagLabel(raw: string, tr: TI18n): string {
  const low = raw.toLowerCase();
  if (low.includes("водяной насос")) return tr("car.accordions.diagCoolantPump");
  if (low.includes("common rail")) return raw.replace(/\s*\(common rail\)\s*/gi, "");
  return raw;
}

function normalizeDiagValue(raw: string, tr: TI18n): string {
  const low = raw.trim().toLowerCase();
  if (low === "нет") return tr("car.accordions.diagOk");
  return raw;
}

function jsonForDiagPreview(v: object): string {
  try {
    const s = JSON.stringify(v);
    if (s.length <= 8000) return s;
    return `${s.slice(0, 8000)}…`;
  } catch {
    return "";
  }
}

function toStructuredDiagRows(
  obj: Record<string, unknown> | undefined,
  tr: TI18n,
): Array<{ label: string; value: string }> {
  if (!obj) return [];
  return Object.entries(obj)
    .map(([k, v]) => {
      const base = asStr(v)
        ? translateKoToRuText(asStr(v)!)
        : typeof v === "object" && v !== null
          ? translateKoToRuText(jsonForDiagPreview(v as object))
          : "";
      const cleaned = cleanScalarText(base);
      if (!cleaned) return null;
      const ruLabel = normalizeDiagLabel(translateKoToRuText(prettifyDataKey(k)), tr);
      const ruValue = normalizeDiagValue(translateKoToRuText(cleaned), tr);
      return { label: ruLabel, value: ruValue };
    })
    .filter((x): x is { label: string; value: string } => Boolean(x));
}

export function CarDetailAccordions({
  data,
  diagnosisPhotosCount,
}: {
  data: Record<string, unknown>;
  diagnosisPhotosCount: number;
}) {
  const { t, locale } = useLocaleContext();
  const i18n = useMemo(() => ({ t, locale }), [t, locale]);
  const reduceMotion = useReducedMotion();
  void diagnosisPhotosCount;
  const extra =
    data.extra && typeof data.extra === "object" && !Array.isArray(data.extra)
      ? (data.extra as Record<string, unknown>)
      : undefined;

  const inspectionRaw = parseJson(getPath(extra, ["inspection"]));
  const inspection =
    inspectionRaw && typeof inspectionRaw === "object" && !Array.isArray(inspectionRaw)
      ? (inspectionRaw as Record<string, unknown>)
      : undefined;
  const masterRaw = parseJson(inspection?.master);
  const master =
    masterRaw && typeof masterRaw === "object" && !Array.isArray(masterRaw)
      ? (masterRaw as Record<string, unknown>)
      : undefined;
  const detail = getPath(master, ["detail"]) as Record<string, unknown> | undefined;

  const mileage =
    formatKm(data.km_age) ??
    formatKm(getPath(detail, ["mileage"])) ??
    formatKm(getPath(extra, ["inspection", "master", "detail", "mileage"]));

  const vin = asStr(data.vin) ?? asStr(getPath(detail, ["vin"]));

  const power =
    ((): string | null => {
      const rec = data as Record<string, unknown>;
      const systemHp =
        parseHp(rec.power_hp) ??
        parseHp(rec.power_hp_system) ??
        parseHp(data.power) ??
        parseHp(data.hp);
      const iceHp = parseHp(rec.power_ice_hp) ?? parseHp(rec.power_kwhp);
      const edHp = parseHp(rec.power_electric_hp) ?? parseHp(rec.power_otherp);
      const layout = String(rec.hybrid_layout ?? "").toLowerCase();
      if (systemHp && iceHp && edHp && layout !== "series") {
        return t("car.accordions.powerHybrid", { system: systemHp, ice: iceHp, ed: edHp });
      }
      if (systemHp && edHp && layout === "series") {
        return t("car.accordions.powerSeries", { system: systemHp, ed: edHp });
      }
      if (systemHp) return t("car.accordions.powerHp", { hp: systemHp });
      const hp = iceHp ?? parseHp(rec.power_kwhp) ?? parseHp(data.power) ?? parseHp(data.hp);
      return hp ? t("car.accordions.powerHp", { hp }) : null;
    })();
  const transmissionRaw =
    normalizeSpecValue(data.transmission_type_ru) ??
    normalizeSpecValue(data.transmission_type) ??
    normalizeSpecValue((data as Record<string, unknown>).gearbox) ??
    normalizeSpecValue((data as Record<string, unknown>).transmission);
  const transmissionSource =
    transmissionRaw && /^\d{1,2}$/.test(transmissionRaw)
      ? (normalizeSpecValue(data.transmission_type) ??
        normalizeSpecValue((data as Record<string, unknown>).gearbox) ??
        normalizeSpecValue((data as Record<string, unknown>).transmission) ??
        transmissionRaw)
      : transmissionRaw;
  const transmission = (() => {
    if (!transmissionSource) return null;
    if (/[а-яёА-ЯЁ]/.test(transmissionSource)) return transmissionSource;
    const mapped = displayTransmission(locale, transmissionSource);
    if (mapped && mapped !== transmissionSource) return mapped;
    if (/^\d{1,2}$/.test(transmissionSource)) return t("car.accordions.transSteps", { n: transmissionSource });
    return mapped ?? transmissionSource;
  })();
  const driveRaw =
    normalizeSpecValue(data.drive_type_ru) ??
    normalizeSpecValue(data.drive_type) ??
    normalizeSpecValue((data as Record<string, unknown>).drivemode) ??
    normalizeSpecValue((data as Record<string, unknown>).drivingmode);
  const drive = driveRaw ? displayDriveType(locale, driveRaw) ?? driveRaw : null;
  const displacementText =
    normalizeSpecValue((data as Record<string, unknown>).displacement) ??
    ((): string | null => {
      const liters = asStr((data as Record<string, unknown>).displacement_liters_label);
      if (liters) return t("car.accordions.liters", { n: liters });
      const cc = Number((data as Record<string, unknown>).displacement_cc);
      return Number.isFinite(cc) && cc > 0 ? t("car.accordions.cc", { n: Math.round(cc) }) : null;
    })();
  const engineLine = asStr((data as Record<string, unknown>).engine);

  const generalRows: { label: string; value: string }[] = [];
  const push = (label: string, v: string | null) => {
    if (v) generalRows.push({ label, value: v });
  };

  push(
    t("car.accordions.fieldTitle"),
    buildNormalizedCarTitle(
      data.mark,
      data.model,
      data.generation ?? data.configuration ?? data.gradeName,
      data.source,
    ) ??
      joinUniqueSpecs(data.mark, data.model, data.generation),
  );
  const trimLine =
    asStr(data.configuration) ??
    asStr(data.gradeName) ??
    asStr((data as Record<string, unknown>).trim_name) ??
    asStr((data as Record<string, unknown>).trim);
  push(t("car.accordions.fieldTrim"), trimLine);
  push(t("car.accordions.fieldYearMonth"), pickRegYearMonthDisplay(data as Record<string, unknown>));
  push(
    t("car.accordions.fieldColor"),
    (() => {
      const cr = asStr(data.color_ru);
      if (cr) return cr;
      const c = asStr(data.color);
      return c ? displayColor(locale, c) ?? c : null;
    })(),
  );
  push(t("car.accordions.fieldMileage"), mileage);
  push("VIN", vin);
  push(
    t("car.accordions.fieldEngine"),
    [engineLine, normalizeFuelLabel(data.engine_type), displacementText].filter(Boolean).join(", ") || null,
  );
  push(t("car.accordions.fieldTransDrive"), [transmission, drive].filter(Boolean).join(", ") || null);
  push(t("car.accordions.fieldPower"), power);
  const torqueNm = Number((data as Record<string, unknown>).torque_nm);
  push(
    t("car.accordions.fieldTorque"),
    Number.isFinite(torqueNm) && torqueNm > 0 ? t("car.accordions.torqueNm", { n: Math.round(torqueNm) }) : null,
  );
  push(t("car.accordions.fieldSeats"), asStr(data.seatCount));

  const paintPartTypes = detail?.paintPartTypes ?? getPath(detail, ["paintPartTypes"]);
  const seriousTypes = detail?.seriousTypes ?? getPath(detail, ["seriousTypes"]);

  const outers = inspection?.outers;

  const accident = master?.accdient ?? master?.accident;
  const simpleRepair = master?.simpleRepair;
  const bodyChanged =
    getPath(extra, ["inspection_structured", "bodyChanged"]) ?? getPath(master, ["bodyChanged"]);
  const inspectionStructuredRaw = parseJson(getPath(extra, ["inspection_structured"]));
  const inspectionStructured =
    inspectionStructuredRaw && typeof inspectionStructuredRaw === "object" && !Array.isArray(inspectionStructuredRaw)
      ? (inspectionStructuredRaw as Record<string, unknown>)
      : undefined;
  const bodyPanels = getPath(inspectionStructured, ["bodyPanels"]);
  const diagnosisRaw = parseJson(getPath(extra, ["diagnosis"]));
  const diagnosis =
    diagnosisRaw && typeof diagnosisRaw === "object" && !Array.isArray(diagnosisRaw)
      ? (diagnosisRaw as Record<string, unknown>)
      : undefined;
  const diagnosisItems = getPath(diagnosis, ["items"]);

  const structured = inspectionStructured;

  const engineTransmission = structured?.engineTransmission as Record<string, unknown> | undefined;
  const chassis = structured?.chassis as Record<string, unknown> | undefined;
  const electrical = structured?.electrical as Record<string, unknown> | undefined;
  const additional = structured?.additional as Record<string, unknown> | undefined;

  const recordOpen =
    extra?.record_open && typeof extra.record_open === "object"
      ? (extra.record_open as Record<string, unknown>)
      : undefined;

  const defaultOpen = ["general"];
  const [openSections, setOpenSections] = useState<string[]>(defaultOpen);

  const sourceKey = String(data.source ?? "").trim().toLowerCase();
  const isChinaListing =
    sourceKey === "che168" || sourceKey.includes("che168") || sourceKey.includes("china");
  const isUsaListing =
    sourceKey === "autotrader" || sourceKey.includes("autotrader") || sourceKey.includes("usa");
  const isKoreaListing = !isChinaListing && !isUsaListing;

  const showEquipment = useMemo(() => listingHasEquipment(data, extra), [data, extra]);
  const showBody = useMemo(() => {
    const hasPayload = hasStructuredBodyPayload(
      bodyPanels,
      outers,
      bodyChanged,
      paintPartTypes,
      seriousTypes,
      diagnosisItems,
    );
    return hasPayload || !isNegativeFlag(accident);
  }, [bodyPanels, outers, bodyChanged, paintPartTypes, seriousTypes, diagnosisItems, accident]);

  const diagSections = useMemo(
    () =>
      [
        { key: "engine", label: t("car.accordions.diagEngine"), rows: toStructuredDiagRows(engineTransmission, t) },
        { key: "chassis", label: t("car.accordions.diagChassis"), rows: toStructuredDiagRows(chassis, t) },
        { key: "electrical", label: t("car.accordions.diagElectrical"), rows: toStructuredDiagRows(electrical, t) },
        { key: "additional", label: t("car.accordions.diagAdditional"), rows: toStructuredDiagRows(additional, t) },
      ].filter((x) => x.rows.length > 0),
    [engineTransmission, chassis, electrical, additional, t],
  );
  const showDiagnosis = diagSections.length > 0;
  const showInsurance = Boolean(recordOpen && Object.keys(recordOpen).length > 0);
  const diagnosisTitle = isKoreaListing
    ? t("car.accordions.sectionDiagnosis")
    : t("car.accordions.sectionDiagnosisDealer");
  const insuranceTitle = isKoreaListing
    ? t("car.accordions.sectionInsurance")
    : t("car.accordions.sectionInsuranceHistory");

  const [activeDiagTab, setActiveDiagTab] = useState<string>(diagSections[0]?.key ?? "engine");
  const activeDiag = diagSections.find((x) => x.key === activeDiagTab) ?? diagSections[0];
  useEffect(() => {
    if (!diagSections.length) return;
    if (!diagSections.some((x) => x.key === activeDiagTab)) {
      setActiveDiagTab(diagSections[0].key);
    }
  }, [diagSections, activeDiagTab]);

  return (
    <CarAccI18nCtx.Provider value={i18n}>
    <Accordion
      type="multiple"
      value={openSections}
      onValueChange={setOpenSections}
      className="mt-6 max-w-full overflow-hidden rounded-none border-0 border-t border-border"
    >
      <AccordionItem value="general">
        <AccordionTrigger className="break-words py-4 ps-0 pe-8 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:no-underline">
          {t("car.accordions.sectionGeneral")}
        </AccordionTrigger>
        <AccordionContent className="px-0">
          <SpecGrid rows={generalRows} />
        </AccordionContent>
      </AccordionItem>

      {/* Priority: overview → condition/history → equipment (options last). */}
      {showBody ? (
        <AccordionItem value="body">
          <AccordionTrigger className="break-words py-4 ps-0 pe-8 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:no-underline">
            {t("car.accordions.sectionBody")}
          </AccordionTrigger>
          <AccordionContent className="px-0">
            {openSections.includes("body") ? (
              <div className="space-y-4">
                <BodyConditionSection
                  outers={outers}
                  bodyPanels={bodyPanels}
                  bodyChanged={bodyChanged}
                  paintPartTypes={paintPartTypes}
                  seriousTypes={seriousTypes}
                  diagnosisItems={diagnosisItems}
                  accident={accident}
                  simpleRepair={simpleRepair}
                />
              </div>
            ) : null}
          </AccordionContent>
        </AccordionItem>
      ) : null}

      {showDiagnosis ? (
        <AccordionItem value="diagnosis">
          <AccordionTrigger className="break-words py-4 ps-0 pe-8 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:no-underline">
            {diagnosisTitle}
          </AccordionTrigger>
          <AccordionContent className="px-0">
            {openSections.includes("diagnosis") ? (
              <div className="space-y-5">
                <div className="space-y-3">
                  <SegmentedControlScroll
                    value={activeDiagTab}
                    onChange={setActiveDiagTab}
                    items={diagSections.map((section) => ({
                      value: section.key,
                      label: section.label,
                    }))}
                    aria-label={t("car.accordions.diagSectionsAria")}
                  />
                  <AnimatePresence mode="wait" initial={false}>
                    {activeDiag ? (
                      <motion.div
                        key={activeDiag.key}
                        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                        transition={{ duration: reduceMotion ? 0 : 0.2, ease: "easeOut" }}
                        className="overflow-hidden"
                      >
                        <ul className="grid grid-cols-1 gap-x-10 md:grid-cols-2">
                          {activeDiag.rows.map((row) => (
                            <li
                              key={`${activeDiag.key}-${row.label}`}
                              className="grid grid-cols-[minmax(0,44%)_minmax(0,1fr)] gap-3 border-b border-border/70 py-2.5 text-sm last:border-b-0 md:[&:nth-last-child(2)]:border-b-0"
                            >
                              <span className="text-muted-foreground">{row.label}</span>
                              <span className="font-medium [overflow-wrap:anywhere]">{row.value}</span>
                            </li>
                          ))}
                        </ul>
                      </motion.div>
                    ) : null}
                  </AnimatePresence>
                </div>
              </div>
            ) : null}
          </AccordionContent>
        </AccordionItem>
      ) : null}

      {showInsurance ? (
        <AccordionItem value="insurance">
          <AccordionTrigger className="break-words py-4 ps-0 pe-8 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:no-underline">
            {insuranceTitle}
          </AccordionTrigger>
          <AccordionContent className="px-0">
            {openSections.includes("insurance") && recordOpen ? (
              <RecordOpenSection ro={recordOpen} />
            ) : null}
          </AccordionContent>
        </AccordionItem>
      ) : null}

      {showEquipment ? (
        <AccordionItem value="equipment">
          <AccordionTrigger className="break-words py-4 ps-0 pe-8 text-start text-base font-semibold tracking-tight [overflow-wrap:anywhere] hover:no-underline">
            {t("car.accordions.sectionEquipment")}
          </AccordionTrigger>
          <AccordionContent className="px-0">
            {openSections.includes("equipment") ? <EquipmentSection d={data} extra={extra} /> : null}
          </AccordionContent>
        </AccordionItem>
      ) : null}

    </Accordion>
    </CarAccI18nCtx.Provider>
  );
}
