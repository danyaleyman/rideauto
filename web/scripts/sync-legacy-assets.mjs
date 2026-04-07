/**
 * Копирует легаси-статику (css/js/image/data) из frontend/ в public/
                              и вытягивает фрагменты car.html для Next /car/[ref].
 * Локально: frontend рядом с web/. В Docker: задайте WRA_FRONTEND_ROOT (путь к копии frontend).
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

function extractFirstStyleBlock(html) {
  const i = html.indexOf("<style>");
  if (i === -1) return "";
  const j = html.indexOf("</style>", i);
  if (j === -1) return "";
  return html.slice(i + "<style>".length, j).trim();
}

function extractCarFragments(html) {
  const analyticsRe = /<script[^>]*\ssrc=["']\/js\/wra-analytics\.js[^"']*["'][^>]*>/;
  const analyticsMatch = html.match(analyticsRe);
  const analyticsIdx = analyticsMatch && analyticsMatch.index != null ? analyticsMatch.index : -1;
  if (analyticsIdx === -1) {
    throw new Error("sync-legacy-assets: cannot find wra-analytics script marker in car.html");
  }
  const bodyMatch = html.match(/<body[^>]*>/);
  if (!bodyMatch || bodyMatch.index === undefined) {
    throw new Error("sync-legacy-assets: no <body> in car.html");
  }
  const bodyStart = bodyMatch.index + bodyMatch[0].length;
  const top = html.slice(bodyStart, analyticsIdx).trim();

  const footMarker = "<!-- Футер как в index.html -->";
  const footI = html.indexOf(footMarker);
  if (footI === -1) {
    throw new Error("sync-legacy-assets: footer marker not found in car.html");
  }
  const footDiv = html.indexOf('<div class="footer-wrap">', footI);
  if (footDiv === -1) {
    throw new Error("sync-legacy-assets: footer-wrap not found in car.html");
  }
  const headerEnd = html.indexOf('<script src="/js/header-init.js"', footDiv);
  if (headerEnd === -1) {
    throw new Error("sync-legacy-assets: header-init script not found in car.html");
  }
  const bottom = html.slice(footDiv, headerEnd).trim();
  return { top, bottom };
}

function main() {
  if (!fs.existsSync(FRONTEND)) {
    console.warn(
      `[sync-legacy-assets] Пропуск копирования: нет каталога frontend (${FRONTEND}).\n` +
        `Укажите WRA_FRONTEND_ROOT или положите репозиторий так, чтобы существовал ../frontend.`,
    );
    return;
  }

  const pub = path.join(WEB_ROOT, "public");
  fs.mkdirSync(pub, { recursive: true });

  for (const name of ["css", "js", "image"]) {
    const src = path.join(FRONTEND, name);
    if (fs.existsSync(src)) copyDir(src, path.join(pub, name));
    else console.warn(`[sync-legacy-assets] нет ${src}`);
  }

  const engineMapSrc = path.join(FRONTEND, "data", "engine_map.json");
  if (fs.existsSync(engineMapSrc)) {
    fs.mkdirSync(path.join(pub, "data"), { recursive: true });
    fs.copyFileSync(engineMapSrc, path.join(pub, "data", "engine_map.json"));
  } else {
    console.warn(`[sync-legacy-assets] нет ${engineMapSrc}`);
  }

  const carHtmlPath = path.join(FRONTEND, "car.html");
  if (!fs.existsSync(carHtmlPath)) {
    console.warn(`[sync-legacy-assets] нет ${carHtmlPath} — фрагменты и inline CSS не обновлены`);
    return;
  }

  const carHtml = fs.readFileSync(carHtmlPath, "utf8");

  const css = extractFirstStyleBlock(carHtml);
  if (css) {
    fs.mkdirSync(path.join(pub, "css"), { recursive: true });
    fs.writeFileSync(path.join(pub, "css", "car-page-inline.css"), css + "\n", "utf8");
  }

  const { top, bottom } = extractCarFragments(carHtml);
  const legDir = path.join(WEB_ROOT, "src", "legacy");
  fs.mkdirSync(legDir, { recursive: true });
  fs.writeFileSync(path.join(legDir, "car-top.fragment.html"), top + "\n", "utf8");
  fs.writeFileSync(path.join(legDir, "car-footer.fragment.html"), bottom + "\n", "utf8");

  console.log("[sync-legacy-assets] ok: public/* + src/legacy/*.fragment.html");
}

main();
