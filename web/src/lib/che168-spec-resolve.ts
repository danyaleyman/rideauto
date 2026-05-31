/** Единая логика извлечения мощности/КПП из che168_params_raw. */

const PLACEHOLDERS = new Set(["--", "-", "—", "null", "none", "n/a", "undefined", ""]);

export const KW_TO_HP = 1.35962;

export function normSpecLabel(s: string): string {
  return s.trim().toLowerCase().replace(/[\s\-_:/()（）[\]【】.+,]+/g, "");
}

export function isSpecPlaceholder(v: unknown): boolean {
  const s = typeof v === "string" ? v.trim().toLowerCase() : "";
  return !s || PLACEHOLDERS.has(s);
}

function* iterDeepNodes(node: unknown): Generator<Record<string, unknown>> {
  if (Array.isArray(node)) {
    for (const x of node) yield* iterDeepNodes(x);
    return;
  }
  if (!node || typeof node !== "object") return;
  const obj = node as Record<string, unknown>;
  yield obj;
  for (const v of Object.values(obj)) yield* iterDeepNodes(v);
}

export function* iterSpecLabelValues(body: unknown): Generator<[string, string]> {
  const nameKeys = ["name", "itemname", "title", "paramname", "specname", "configName", "key", "label"];
  const valueKeys = ["value", "dispvalue", "paramvalue", "specvalue", "subvalue", "text", "val"];
  for (const node of iterDeepNodes(body)) {
    let label: string | null = null;
    for (const nk of nameKeys) {
      const cand = node[nk];
      if (typeof cand === "string" && cand.trim()) {
        label = cand.trim();
        break;
      }
    }
    if (!label) continue;
    for (const vk of valueKeys) {
      const vv = node[vk];
      if (vv != null && String(vv).trim() && !isSpecPlaceholder(vv)) {
        yield [label, String(vv).trim()];
        break;
      }
    }
  }
}

/** HP из строки двигателя: «1.2T 116HP L4», «258hp». */
export function extractHpFromEngineText(text: string): number | null {
  const s = text.trim();
  if (!s) return null;
  const tagged = /(\d{2,4})\s*(?:HP|hp|PS|ps|л\.?с\.?|马力)/i.exec(s);
  if (tagged) {
    const n = Number(tagged[1]);
    if (Number.isFinite(n) && n >= 30 && n <= 2000) return n;
  }
  return null;
}

type PowerLabelKind = "hp" | "kw" | "engine" | "skip";

/** Классификация поля specparam — без ложных срабатываний (speed ⊃ ps). */
export function classifyChe168PowerLabel(label: string): PowerLabelKind {
  const n = normSpecLabel(label);
  if (!n) return "skip";
  if (n.includes("torque") || n.includes("扭矩")) return "skip";
  if (n.includes("rpm")) return "skip";
  if (n.includes("topspeed") || n.includes("maxspeed") || n.includes("最高车速") || n.includes("最高速度"))
    return "skip";
  if (n.includes("powersteering") || n.includes("steeringtype")) return "skip";
  if (n === "engine" || n === "enginetype" || n.includes("发动机")) return "engine";
  if (n.includes("kw") || n.includes("千瓦") || n.includes("maximumnetpower")) return "kw";
  if (
    n.includes("horsepower") ||
    n.includes("最大马力") ||
    n.includes("maximumhorsepower") ||
    n.includes("maxhorsepower") ||
    n.endsWith("hp") ||
    n.includes("马力")
  ) {
    return "hp";
  }
  if (/\bps\b/.test(label) || n.endsWith("ps")) return "hp";
  if (n.includes("power") || n.includes("功率")) return "kw";
  return "skip";
}

function parseSpecNumber(val: string): number | null {
  const m = /(\d{2,4})/.exec(val.replace(/,/g, ""));
  if (!m) return null;
  const n = Number(m[1]);
  if (!Number.isFinite(n) || n < 30 || n > 2000) return null;
  return n;
}

/**
 * Мощность в л.с.: Engine HP → Ps/HP поля → kW×1.36.
 * Не путать с top speed, torque, kW как л.с.
 */
export function resolveChe168PowerHp(body: unknown, engineText = ""): number | null {
  const fromEngineField = extractHpFromEngineText(engineText);
  if (fromEngineField != null) return fromEngineField;

  let engineFromSpec: number | null = null;
  const hpExplicit: number[] = [];
  const kwVals: number[] = [];

  for (const [label, val] of iterSpecLabelValues(body)) {
    const kind = classifyChe168PowerLabel(label);
    const num = parseSpecNumber(val);
    if (num == null) continue;
    if (kind === "engine") {
      const hp = extractHpFromEngineText(val);
      if (hp != null) engineFromSpec = hp;
    } else if (kind === "hp") {
      hpExplicit.push(num);
    } else if (kind === "kw") {
      kwVals.push(num);
    }
  }

  if (engineFromSpec != null) return engineFromSpec;
  if (hpExplicit.length) return Math.max(...hpExplicit);
  if (kwVals.length) return Math.round(Math.max(...kwVals) * KW_TO_HP);
  return null;
}

export function resolveChe168TorqueNm(body: unknown): number | null {
  for (const [label, val] of iterSpecLabelValues(body)) {
    const n = normSpecLabel(label);
    if (!n.includes("torque") && !n.includes("扭矩")) continue;
    if (n.includes("rpm")) continue;
    const num = parseSpecNumber(val);
    if (num != null && num >= 50 && num <= 2000) return num;
  }
  return null;
}

export function resolveChe168Gearbox(body: unknown, current?: unknown): string | null {
  const candidates: string[] = [];
  for (const [label, val] of iterSpecLabelValues(body)) {
    const n = normSpecLabel(label);
    if (
      n.includes("abbreviation") ||
      n.includes("transmissiontype") ||
      (n.includes("transmission") && !n.includes("speed")) ||
      n.includes("gearbox") ||
      n.includes("变速箱") ||
      n.includes("变速器")
    ) {
      candidates.push(val);
    }
  }
  const rich = candidates.filter((c) => c.length > 4 && !/^\d{1,2}$/.test(c));
  if (rich.length) return rich.sort((a, b) => b.length - a.length)[0]!;
  const cur = typeof current === "string" ? current.trim() : "";
  if (cur && !isSpecPlaceholder(cur) && !/^\d{1,2}$/.test(cur)) return cur;
  if (candidates.length) return candidates[candidates.length - 1]!;
  return cur && !isSpecPlaceholder(cur) ? cur : null;
}

export function resolveChe168Drive(body: unknown, current?: unknown): string | null {
  if (current != null && !isSpecPlaceholder(current)) return String(current).trim();
  for (const [label, val] of iterSpecLabelValues(body)) {
    const n = normSpecLabel(label);
    if (n.includes("drivetype") || n.includes("drivemode") || n.includes("drivetrain") || n.includes("驱动")) {
      return val;
    }
  }
  return null;
}

export function resolveChe168DisplacementLiters(body: unknown): string | null {
  for (const [label, val] of iterSpecLabelValues(body)) {
    const n = normSpecLabel(label);
    if (n.includes("displacementml") || n.includes("displacementcc") || n.endsWith("ml")) continue;
    if (n.includes("displacementl") || (n.includes("displacement") && n.endsWith("l"))) {
      const m = /(\d+(?:[.,]\d)?)/.exec(val);
      if (m) return m[1]!.replace(",", ".");
    }
  }
  return null;
}
