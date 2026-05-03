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

/** Локализованные строки по пути ``catalog.empty.title`` с fallback на ru. */
export function createT(locale: AppLocale): (path: string) => string {
  const primary = bundles[locale];
  const fallback = bundles.ru;
  return (path: string) => {
    const parts = path.split(".");
    return walk(primary, parts) ?? walk(fallback, parts) ?? path;
  };
}

/** Только ru — для мест без контекста локали (постепенно заменяйте на ``createT``). */
export function t(path: string): string {
  return createT("ru")(path);
}
