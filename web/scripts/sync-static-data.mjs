/**
 * Copies static lookup data from `data/` to `web/public/data` before dev/build.
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
    console.warn(`[sync-static-data] skip: no ${DATA}`);
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
    console.warn("[sync-static-data] no engine_map.json / encar_mapping.json in data/");
    return;
  }
  console.log(`[sync-static-data] ok (${n} file(s) -> web/public/data/)`);
}

main();
