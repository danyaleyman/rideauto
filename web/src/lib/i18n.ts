import ru from "../../messages/ru.json";

type MessageTree = Record<string, unknown>;

function walk(obj: unknown, parts: string[]): string | undefined {
  let cur: unknown = obj;
  for (const p of parts) {
    if (!cur || typeof cur !== "object") return undefined;
    cur = (cur as MessageTree)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

/** Тексты UI по пути вида ``catalog.empty.title`` (заготовка под полноценный i18n). */
export function t(path: string): string {
  const s = walk(ru as MessageTree, path.split("."));
  return s ?? path;
}
