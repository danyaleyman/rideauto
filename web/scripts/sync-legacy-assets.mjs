/**
 * Sync selected legacy static assets into web/public before dev/build.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, "..");
const FRONTEND = (
  process.env.WRA_FRONTEND_ROOT?.trim() || path.resolve(WEB_ROOT, "..", "frontend")
).replace(/\/+$/, "");

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const ent of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, ent.name);
    const d = path.join(dest, ent.name);
    if (ent.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function main() {
  if (!fs.existsSync(FRONTEND)) {
    console.warn(`[sync-legacy-assets] skip: frontend not found (${FRONTEND})`);
    return;
  }

  const pub = path.join(WEB_ROOT, "public");
  fs.mkdirSync(pub, { recursive: true });

  for (const name of ["css", "js", "image"]) {
    const src = path.join(FRONTEND, name);
    if (fs.existsSync(src)) copyDir(src, path.join(pub, name));
  }

  const engineMapSrc = path.join(FRONTEND, "data", "engine_map.json");
  if (fs.existsSync(engineMapSrc)) {
    fs.mkdirSync(path.join(pub, "data"), { recursive: true });
    fs.copyFileSync(engineMapSrc, path.join(pub, "data", "engine_map.json"));
  }

  const seoSrc = path.join(FRONTEND, "seo");
  if (fs.existsSync(seoSrc)) {
    copyDir(seoSrc, path.join(pub, "seo"));
  }

  console.log("[sync-legacy-assets] ok");
}

main();
