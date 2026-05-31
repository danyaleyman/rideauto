import en from "../../messages/en.json";
import ru from "../../messages/ru.json";

export type AppLocale = "ru" | "en";

type MessageTree = Record<string, unknown>;

const bundles: Record<AppLocale, MessageTree> = {
  ru: ru as MessageTree,
  en: en as MessageTree,
};

function walk(obj: unknown, parts: string[]): string | undefined {
  let cur: unknown = obj;
  for (const p of parts) {
    if (!cur || typeof cur !== "object") return undefined;
    cur = (cur as MessageTree)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

export type TParams = Record<string, string | number>;

function applyParams(template: string, params?: TParams): string {
  if (!params) return template;
  let out = template;
  for (const [key, value] of Object.entries(params)) {
    out = out.replaceAll(`{${key}}`, String(value));
  }
  return out;
}

/** Локализованные строки по пути ``catalog.empty.title`` с fallback на ru. */
export function createT(locale: AppLocale): (path: string, params?: TParams) => string {
  const primary = bundles[locale];
  const fallback = bundles.ru;
  return (path: string, params?: TParams) => {
    const parts = path.split(".");
    const raw = walk(primary, parts) ?? walk(fallback, parts) ?? path;
    return applyParams(raw, params);
  };
}

/** Только ru — для мест без контекста локали (постепенно заменяйте на ``createT``). */
export function t(path: string): string {
  return createT("ru")(path);
}
