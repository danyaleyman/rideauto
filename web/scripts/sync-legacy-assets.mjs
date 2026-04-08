/**
 * Копирует статические данные из `data/` в `web/public/data` перед dev/build.
 * (Каталог живёт в Postgres; опциональный `web/public/cars.json` пишет postgres_catalog_sync.)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(WEB_ROOT, "..");
const DATA = path.join(REPO_ROOT, "data");
const pubData = path.join(WEB_ROOT, "public", "data");

function main() {
  if (!fs.existsSync(DATA)) {
    console.warn(`[sync-legacy-assets] skip: no ${DATA}`);
    return;
  }
  fs.mkdirSync(pubData, { recursive: true });
  const names = ["engine_map.json", "encar_mapping.json"];
  let n = 0;
  for (const name of names) {
    const src = path.join(DATA, name);
    if (!fs.existsSync(src)) continue;
    fs.copyFileSync(src, path.join(pubData, name));
    n += 1;
  }
  if (n === 0) {
    console.warn("[sync-legacy-assets] no engine_map.json / encar_mapping.json in data/");
    return;
  }
  console.log(`[sync-legacy-assets] ok (${n} file(s) → web/public/data/)`);
}

main();
