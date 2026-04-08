#!/usr/bin/env node
/**
 * Статические SEO-посадки под марку / марку+модель (корейский каталог Encar).
 *
 *   node scripts/generate-seo-landings.mjs
 *
 * Читает data/seo-landings.json, пишет HTML в web/public/seo/korea/<mark>/<model>/index.html
 * и обновляет блок URL в web/public/sitemap-pages.xml.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const DATA_PATH = path.join(ROOT, "data", "seo-landings.json");
const OUT_ROOT = path.join(ROOT, "web", "public", "seo", "korea");
const SITEMAP_PATH = path.join(ROOT, "web", "public", "sitemap-pages.xml");
const SITEMAP_FALLBACK = path.join(ROOT, "web", "public", "sitemap-pages.xml");

function slug(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/"/g, "&quot;");
}

function catalogQueryMarkOnly(markValue) {
  const p = new URLSearchParams();
  p.set("marks", markValue);
  return "/?" + p.toString();
}

function catalogQueryMarkModel(markValue, modelValue) {
  const p = new URLSearchParams();
  p.set("marks", markValue);
  p.set("models", modelValue);
  return "/?" + p.toString();
}

function pageTemplate(opts) {
  const {
    title,
    description,
    canonical,
    h1,
    lead,
    catalogUrl,
    jsonLd,
  } = opts;
  return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escHtml(title)}</title>
  <meta name="description" content="${escHtml(description)}">
  <link rel="canonical" href="${escHtml(canonical)}">
  <link rel="stylesheet" href="/css/common.css?v=20260423">
  <script type="application/ld+json">
${JSON.stringify(jsonLd, null, 2)}
  </script>
</head>
<body>
  <a href="#main" class="skip-link">К содержанию</a>
  <header class="header">
    <div class="header-content">
      <a href="/" class="logo"><img src="/image/logo.svg" alt="World Ride Auto" width="120" height="32"></a>
      <nav class="nav-menu" aria-label="Разделы">
        <a href="/about">О компании</a>
        <a href="/catalog">Каталог</a>
        <a href="/buy">Как купить</a>
        <a href="/contacts">Контакты</a>
      </nav>
      <div class="header-buttons">
        <a href="https://t.me/nikits15" class="btn btn-primary" target="_blank" rel="noopener">Связаться</a>
      </div>
    </div>
  </header>
  <main id="main" class="wra-seo-landing">
    <h1>${escHtml(h1)}</h1>
    <p class="wra-seo-lead">${escHtml(lead)}</p>
    <div class="wra-seo-actions">
      <a class="btn btn-primary" href="${escHtml(catalogUrl)}">Смотреть объявления в каталоге</a>
      <a class="btn btn-secondary" href="/catalog">Все авто из Кореи</a>
    </div>
    <p class="wra-seo-note">World Ride Auto — подбор автомобилей с Encar, ориентиры по ценам и доставке во Владивосток. Точные суммы зависят от курса и комплектации; уточняйте у менеджера.</p>
  </main>
  <footer class="footer-wrap" style="margin-top:48px">
    <div class="footer-top wra-container" style="border-top:1px solid var(--wra-border);padding-top:24px">
      <p class="wra-seo-note" style="margin:0">&copy; World Ride Auto 2026 · <a href="/privacy">Конфиденциальность</a></p>
    </div>
  </footer>
</body>
</html>
`;
}

function ensureDir(d) {
  fs.mkdirSync(d, { recursive: true });
}

function main() {
  ensureDir(path.dirname(SITEMAP_PATH));
  if (!fs.existsSync(SITEMAP_PATH)) {
    if (fs.existsSync(SITEMAP_FALLBACK)) {
      fs.copyFileSync(SITEMAP_FALLBACK, SITEMAP_PATH);
    } else {
      fs.writeFileSync(
        SITEMAP_PATH,
        `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <!-- WRA_SEO_KOREA_LANDINGS_BEGIN -->
  <!-- WRA_SEO_KOREA_LANDINGS_END -->
</urlset>
`,
        "utf8"
      );
    }
  }

  const raw = fs.readFileSync(DATA_PATH, "utf8");
  const data = JSON.parse(raw);
  const base = (data.baseUrl || "https://rideauto.ru").replace(/\/+$/, "");
  const urls = [];

  fs.rmSync(OUT_ROOT, { recursive: true, force: true });
  ensureDir(OUT_ROOT);

  for (const m of data.markPages || []) {
    const ms = slug(m.markValue);
    const dir = path.join(OUT_ROOT, ms);
    ensureDir(dir);
    const canonical = `${base}/seo/korea/${ms}/`;
    const catalogUrl = catalogQueryMarkOnly(m.markValue);
    const h1 = `${m.markValue} — авто из Кореи`;
    const lead =
      m.description ||
      `Подбор ${m.markValue} на корейской площадке Encar: фильтры по году, пробегу и цене.`;
    const jsonLd = {
      "@context": "https://schema.org",
      "@type": "WebPage",
      name: m.title,
      description: m.description,
      url: canonical,
      isPartOf: { "@type": "WebSite", name: "World Ride Auto", url: base + "/" },
    };
    const html = pageTemplate({
      title: m.title,
      description: m.description,
      canonical,
      h1,
      lead,
      catalogUrl,
      jsonLd,
    });
    fs.writeFileSync(path.join(dir, "index.html"), html, "utf8");
    urls.push(canonical);
  }

  for (const row of data.modelPages || []) {
    const ms = slug(row.markValue);
    const mo = slug(row.modelValue);
    const dir = path.join(OUT_ROOT, ms, mo);
    ensureDir(dir);
    const canonical = `${base}/seo/korea/${ms}/${mo}/`;
    const catalogUrl = catalogQueryMarkModel(row.markValue, row.modelValue);
    const h1 = `${row.markValue} ${row.modelValue} — из Кореи`;
    const lead =
      row.description ||
      `Актуальные объявления ${row.markValue} ${row.modelValue} в каталоге World Ride Auto.`;
    const jsonLd = {
      "@context": "https://schema.org",
      "@type": "WebPage",
      name: row.title,
      description: row.description,
      url: canonical,
      isPartOf: { "@type": "WebSite", name: "World Ride Auto", url: base + "/" },
    };
    const html = pageTemplate({
      title: row.title,
      description: row.description,
      canonical,
      h1,
      lead,
      catalogUrl,
      jsonLd,
    });
    fs.writeFileSync(path.join(dir, "index.html"), html, "utf8");
    urls.push(canonical);
  }

  urls.sort();
  const urlXml = urls
    .map(
      (loc) => `  <url>
    <loc>${loc}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.75</priority>
  </url>`
    )
    .join("\n");

  let sitemap = fs.readFileSync(SITEMAP_PATH, "utf8");
  const begin = "<!-- WRA_SEO_KOREA_LANDINGS_BEGIN -->";
  const end = "<!-- WRA_SEO_KOREA_LANDINGS_END -->";
  if (!sitemap.includes(begin)) {
    sitemap = sitemap.replace("</urlset>", `  ${begin}\n  ${end}\n</urlset>`);
  }
  const re = new RegExp(
    `${begin}[\\s\\S]*?${end}`,
    "m"
  );
  sitemap = sitemap.replace(
    re,
    `${begin}\n${urlXml}\n  ${end}`
  );
  fs.writeFileSync(SITEMAP_PATH, sitemap, "utf8");

  console.log("OK: SEO landings →", OUT_ROOT, "count=", urls.length, "sitemap-pages.xml updated");
}

main();
