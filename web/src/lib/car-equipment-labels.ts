import { asStr, cleanScalarText, getPath, translateKoToRuText } from "@/lib/car-detail-data";
import { displayChinaOptionRu, isChinaOptionNoise } from "@/lib/china-options-display";

const CYRILLIC_RE = /[\u0400-\u04FF]/;
import {
  collectSelectedEncarOptions,
  displayEncarStandardOption,
} from "@/lib/encar-options-display";

function parseJson(v: unknown): unknown {
  if (typeof v !== "string") return v;
  try {
    return JSON.parse(v) as unknown;
  } catch {
    return null;
  }
}

function isMeaningfulOptionLabel(v: string): boolean {
  const t = v.trim();
  if (!t || /^\d+$/.test(t)) return false;
  if (CYRILLIC_RE.test(t)) return true;
  if (isChinaOptionNoise(v)) return false;
  if (/^[\W_]+$/.test(t)) return false;
  return true;
}

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

/** Все подписи опций/комплектации для карточки (Encar + China), в стабильном порядке. */
export function collectCarEquipmentLabels(data: Record<string, unknown>): string[] {
  const extra =
    data.extra && typeof data.extra === "object" && !Array.isArray(data.extra)
      ? (data.extra as Record<string, unknown>)
      : undefined;
  const options = data.options as Record<string, unknown> | undefined;
  const standard = options?.standard;
  const codes = Array.isArray(standard) ? standard : [];

  const chinaRecommendedRaw = parseJson(
    data.options_real ?? data.che168_recommended_options ?? data.che168_options_enriched,
  );
  const chinaRecommendedFallback = collectChinaHighlightLabels(data);
  const chinaRecommended: string[] = (() => {
    if (!Array.isArray(chinaRecommendedRaw)) return chinaRecommendedFallback;
    const out: string[] = [];
    const seen = new Set<string>();
    for (const item of chinaRecommendedRaw) {
      if (typeof item === "string") {
        const t = item.trim();
        if (t && !seen.has(t) && isMeaningfulOptionLabel(t)) {
          seen.add(t);
          out.push(t);
        }
        continue;
      }
      const raw =
        item && typeof item === "object"
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
      out.push(ru);
    }
    return out.length ? out : chinaRecommendedFallback;
  })();

  const sp = getPath(extra, ["sellingpoint"]) as Record<string, unknown> | undefined;
  const uniquePhotos = getPath(sp, ["uniqueOptionPhotos"]);
  const choicePhotos = getPath(sp, ["choiceOptionPhotos"]);
  const selectedOptions = collectSelectedEncarOptions(uniquePhotos, choicePhotos, extra, data);

  const seen = new Set<string>();
  const out: string[] = [];
  const push = (v: string) => {
    const t = cleanScalarText(v);
    if (!t || /^Опция\s+\d+$/i.test(t) || seen.has(t)) return;
    seen.add(t);
    out.push(t);
  };

  for (const v of chinaRecommended) push(v);
  for (const row of selectedOptions) {
    const lb = cleanScalarText(row.label);
    if (lb) push(lb);
  }
  for (const c of codes) {
    const label = cleanScalarText(displayEncarStandardOption(c, uniquePhotos, choicePhotos, extra, data));
    if (label) push(label);
  }
  return out;
}
