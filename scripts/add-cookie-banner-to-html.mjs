/**
 * Вставляет баннер cookie + подгрузку маркетинговых пикселей на все .html без cookie-consent.
 * SEO-страницы (/frontend/seo/) — абсолютные пути /js/ /css/; остальные в корне frontend — относительные.
 */
import fs from "node:fs";
import path from "node:path";

const frontend = path.join(process.cwd(), "frontend");

function walk(dir, out = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, out);
    else if (ent.name.endsWith(".html")) out.push(p);
  }
  return out;
}

const snippetRel =
  "\n  <script src=\"js/wra-site-config.js?v=20260421\" defer></script>\n" +
  '  <link rel="stylesheet" href="css/cookie-consent.css?v=20260410">\n' +
  '  <script src="js/cookie-consent.js?v=20260421" defer></script>\n';

const snippetAbs =
  "\n  <script src=\"/js/wra-site-config.js?v=20260421\" defer></script>\n" +
  '  <link rel="stylesheet" href="/css/cookie-consent.css?v=20260410">\n' +
  '  <script src="/js/cookie-consent.js?v=20260421" defer></script>\n';

let n = 0;
for (const file of walk(frontend)) {
  let t = fs.readFileSync(file, "utf8");
  if (t.includes("cookie-consent.js")) continue;
  if (!t.includes("</body>")) {
    console.warn("skip (no </body>):", path.relative(process.cwd(), file));
    continue;
  }
  const isSeo = file.split(path.sep).includes("seo");
  const snip = isSeo ? snippetAbs : snippetRel;
  t = t.replace("</body>", snip + "</body>");
  fs.writeFileSync(file, t);
  n++;
}
console.log("patched", n, "html files");
