#!/usr/bin/env node
/**
 * Статические SEO-посадки (RU + EN) с hreflang.
 *
 *   node scripts/generate-seo-landings.mjs
 *
 * Читает data/seo-landings.json, пишет:
 *   web/public/seo/korea/<mark>/...
 *   web/public/seo/en/korea/<mark>/...
 * и обновляет блок URL в web/public/sitemap-pages.xml.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const DATA_PATH = path.join(ROOT, "data", "seo-landings.json");
const OUT_RU = path.join(ROOT, "web", "public", "seo", "korea");
const OUT_EN = path.join(ROOT, "web", "public", "seo", "en", "korea");
const SITEMAP_PATH = path.join(ROOT, "web", "public", "sitemap-pages.xml");

const UI = {
  ru: {
    skip: "К содержанию",
    navAria: "Разделы",
    about: "О компании",
    catalog: "Каталог",
    buy: "Как купить",
    contacts: "Контакты",
    contactCta: "Связаться",
    catalogCta: "Смотреть объявления в каталоге",
    allKorea: "Все авто из Кореи",
    note:
      "World Ride Auto — подбор автомобилей из Кореи, ориентиры по ценам и доставке во Владивосток. Точные суммы зависят от курса и комплектации; уточняйте у менеджера.",
    privacy: "Конфиденциальность",
    markH1: (mark) => `${mark} — авто из Кореи`,
    markLead: (mark) =>
      `Подбор ${mark} на корейском рынке: фильтры по году, пробегу и цене.`,
    modelH1: (mark, model) => `${mark} ${model} — из Кореи`,
    modelLead: (mark, model) =>
      `Актуальные объявления ${mark} ${model} в каталоге World Ride Auto.`,
    markTitle: (mark) => `${mark} из Кореи — купить автомобиль с доставкой во Владивосток`,
    markDesc: (mark) =>
      `Каталог ${mark} с корейского рынка: подбор по модели, цены «под ключ», доставка и оформление через World Ride Auto.`,
    modelTitle: (mark, model) => `${mark} ${model} из Кореи — каталог World Ride Auto`,
    modelDesc: (mark, model) =>
      `${mark} ${model} с корейского рынка. Фильтры по году, пробегу и комплектации в каталоге World Ride Auto.`,
  },
  en: {
    skip: "Skip to content",
    navAria: "Sections",
    about: "About",
    catalog: "Catalog",
    buy: "How to buy",
    contacts: "Contacts",
    contactCta: "Contact us",
    catalogCta: "Browse listings in catalog",
    allKorea: "All cars from Korea",
    note:
      "World Ride Auto — sourcing cars from Korea, price guidance and delivery to Vladivostok. Final amounts depend on FX and trim; ask a manager for details.",
    privacy: "Privacy",
    markH1: (mark) => `${mark} — cars from Korea`,
    markLead: (mark) =>
      `Browse ${mark} on the Korean market: filter by year, mileage and price.`,
    modelH1: (mark, model) => `${mark} ${model} — from Korea`,
    modelLead: (mark, model) =>
      `Current ${mark} ${model} listings in the World Ride Auto catalog.`,
    markTitle: (mark) => `${mark} from Korea — import with delivery to Vladivostok`,
    markDesc: (mark) =>
      `${mark} catalog from Korea: model filters, turnkey pricing, delivery and paperwork with World Ride Auto.`,
    modelTitle: (mark, model) => `${mark} ${model} from Korea — World Ride Auto catalog`,
    modelDesc: (mark, model) =>
      `${mark} ${model} from the Korean market. Filter by year, mileage and trim in our catalog.`,
  },
};

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
  return "/catalog?" + p.toString();
}

function catalogQueryMarkModel(markValue, modelValue) {
  const p = new URLSearchParams();
  p.set("marks", markValue);
  p.set("models", modelValue);
  return "/catalog?" + p.toString();
}

function hreflangLinks(canonicalRu, canonicalEn) {
  return `
  <link rel="alternate" hreflang="ru" href="${escHtml(canonicalRu)}">
  <link rel="alternate" hreflang="en" href="${escHtml(canonicalEn)}">
  <link rel="alternate" hreflang="x-default" href="${escHtml(canonicalRu)}">`;
}

function pageTemplate(opts) {
  const {
    lang,
    title,
    description,
    canonical,
    alternateRu,
    alternateEn,
    h1,
    lead,
    catalogUrl,
    jsonLd,
  } = opts;
  const ui = UI[lang];
  const catalogAll = lang === "en" ? "/catalog?lang=en" : "/catalog";
  return `<!DOCTYPE html>
<html lang="${lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escHtml(title)}</title>
  <meta name="description" content="${escHtml(description)}">
  <link rel="canonical" href="${escHtml(canonical)}">${hreflangLinks(alternateRu, alternateEn)}
  <link rel="stylesheet" href="/css/common.css?v=20260423">
  <script type="application/ld+json">
${JSON.stringify(jsonLd, null, 2)}
  </script>
</head>
<body>
  <a href="#main" class="skip-link">${escHtml(ui.skip)}</a>
  <header class="header">
    <div class="header-content">
      <a href="/" class="logo"><img src="/image/logo.svg" alt="World Ride Auto" width="120" height="32"></a>
      <nav class="nav-menu" aria-label="${escHtml(ui.navAria)}">
        <a href="/about">${escHtml(ui.about)}</a>
        <a href="${escHtml(catalogAll)}">${escHtml(ui.catalog)}</a>
        <a href="/buy">${escHtml(ui.buy)}</a>
        <a href="/contacts">${escHtml(ui.contacts)}</a>
      </nav>
      <div class="header-buttons">
        <a href="https://t.me/nikits15" class="btn btn-primary" target="_blank" rel="noopener">${escHtml(ui.contactCta)}</a>
      </div>
    </div>
  </header>
  <main id="main" class="wra-seo-landing">
    <h1>${escHtml(h1)}</h1>
    <p class="wra-seo-lead">${escHtml(lead)}</p>
    <div class="wra-seo-actions">
      <a class="btn btn-primary" href="${escHtml(catalogUrl)}">${escHtml(ui.catalogCta)}</a>
      <a class="btn btn-secondary" href="${escHtml(catalogAll)}">${escHtml(ui.allKorea)}</a>
    </div>
    <p class="wra-seo-note">${escHtml(ui.note)}</p>
  </main>
  <footer class="footer-wrap" style="margin-top:48px">
    <div class="footer-top wra-container" style="border-top:1px solid var(--wra-border);padding-top:24px">
      <p class="wra-seo-note" style="margin:0">&copy; World Ride Auto 2026 · <a href="/privacy">${escHtml(ui.privacy)}</a></p>
    </div>
  </footer>
</body>
</html>
`;
}

function ensureDir(d) {
  fs.mkdirSync(d, { recursive: true });
}

function writeLanding({ outDir, lang, base, pathSeg, page }) {
  const dir = path.join(outDir, pathSeg);
  ensureDir(dir);
  const canonical = `${base}/seo/${lang === "en" ? "en/korea" : "korea"}/${pathSeg}/`;
  const alternateRu = `${base}/seo/korea/${pathSeg}/`;
  const alternateEn = `${base}/seo/en/korea/${pathSeg}/`;
  const ui = UI[lang];
  const title = page.title || (page.modelValue ? ui.modelTitle(page.markValue, page.modelValue) : ui.markTitle(page.markValue));
  const description =
    page.description ||
    (page.modelValue
      ? ui.modelDesc(page.markValue, page.modelValue)
      : ui.markDesc(page.markValue));
  const h1 = page.h1 || (page.modelValue ? ui.modelH1(page.markValue, page.modelValue) : ui.markH1(page.markValue));
  const lead =
    page.lead ||
    (page.modelValue ? ui.modelLead(page.markValue, page.modelValue) : ui.markLead(page.markValue));
  const catalogUrl = page.catalogUrl;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: title,
    description,
    url: canonical,
    inLanguage: lang === "en" ? "en" : "ru",
    isPartOf: { "@type": "WebSite", name: "World Ride Auto", url: base + "/" },
  };
  const html = pageTemplate({
    lang,
    title,
    description,
    canonical,
    alternateRu,
    alternateEn,
    h1,
    lead,
    catalogUrl,
    jsonLd,
  });
  fs.writeFileSync(path.join(dir, "index.html"), html, "utf8");
  return canonical;
}

function main() {
  if (!fs.existsSync(SITEMAP_PATH)) {
    fs.writeFileSync(
      SITEMAP_PATH,
      `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <!-- WRA_SEO_KOREA_LANDINGS_BEGIN -->
  <!-- WRA_SEO_KOREA_LANDINGS_END -->
</urlset>
`,
      "utf8",
    );
  }

  const raw = fs.readFileSync(DATA_PATH, "utf8");
  const data = JSON.parse(raw);
  const base = (data.baseUrl || "https://rideauto.ru").replace(/\/+$/, "");
  const urls = [];

  fs.rmSync(OUT_RU, { recursive: true, force: true });
  fs.rmSync(OUT_EN, { recursive: true, force: true });
  ensureDir(OUT_RU);
  ensureDir(OUT_EN);

  for (const m of data.markPages || []) {
    const ms = slug(m.markValue);
    const catalogUrl = catalogQueryMarkOnly(m.markValue);
    const page = {
      markValue: m.markValue,
      title: m.title,
      titleEn: m.titleEn,
      description: m.description,
      descriptionEn: m.descriptionEn,
      catalogUrl,
    };
    urls.push(
      writeLanding({
        outDir: OUT_RU,
        lang: "ru",
        base,
        pathSeg: ms,
        page: { ...page, title: m.title, description: m.description },
      }),
    );
    urls.push(
      writeLanding({
        outDir: OUT_EN,
        lang: "en",
        base,
        pathSeg: ms,
        page: {
          ...page,
          title: m.titleEn || UI.en.markTitle(m.markValue),
          description: m.descriptionEn || UI.en.markDesc(m.markValue),
        },
      }),
    );
  }

  for (const row of data.modelPages || []) {
    const ms = slug(row.markValue);
    const mo = slug(row.modelValue);
    const pathSeg = `${ms}/${mo}`;
    const catalogUrl = catalogQueryMarkModel(row.markValue, row.modelValue);
    const page = {
      markValue: row.markValue,
      modelValue: row.modelValue,
      catalogUrl,
    };
    urls.push(
      writeLanding({
        outDir: OUT_RU,
        lang: "ru",
        base,
        pathSeg,
        page: { ...page, title: row.title, description: row.description },
      }),
    );
    urls.push(
      writeLanding({
        outDir: OUT_EN,
        lang: "en",
        base,
        pathSeg,
        page: {
          ...page,
          title: row.titleEn || UI.en.modelTitle(row.markValue, row.modelValue),
          description: row.descriptionEn || UI.en.modelDesc(row.markValue, row.modelValue),
        },
      }),
    );
  }

  urls.sort();
  const urlXml = urls
    .map(
      (loc) => `  <url>
    <loc>${loc}</loc>
    <changefreq>weekly</changefreq>
    <priority>0.75</priority>
  </url>`,
    )
    .join("\n");

  let sitemap = fs.readFileSync(SITEMAP_PATH, "utf8");
  const begin = "<!-- WRA_SEO_KOREA_LANDINGS_BEGIN -->";
  const end = "<!-- WRA_SEO_KOREA_LANDINGS_END -->";
  if (!sitemap.includes(begin)) {
    sitemap = sitemap.replace("</urlset>", `  ${begin}\n  ${end}\n</urlset>`);
  }
  const re = new RegExp(`${begin}[\\s\\S]*?${end}`, "m");
  sitemap = sitemap.replace(re, `${begin}\n${urlXml}\n  ${end}`);
  fs.writeFileSync(SITEMAP_PATH, sitemap, "utf8");

  console.log("OK: SEO landings RU →", OUT_RU, "EN →", OUT_EN, "urls=", urls.length);
}

main();
