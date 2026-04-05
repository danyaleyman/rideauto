#!/usr/bin/env node
/**
 * Заменить суффикс ?v=... у car-page-dicts.js и car-page.js во frontend/*.html.
 * Использование: node scripts/bump-asset-version.mjs 20260406car
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const ver = process.argv[2];
if (!ver || !/^[a-zA-Z0-9._-]+$/.test(ver)) {
  console.error("Usage: node scripts/bump-asset-version.mjs <newVersion>");
  process.exit(1);
}

const htmlDir = path.join(root, "frontend");
const files = fs.readdirSync(htmlDir).filter((f) => f.endsWith(".html"));
const re = /(car-page(?:-dicts)?\.js\?v=)([^"'&\s]+)/g;
let changed = 0;
for (const f of files) {
  const fp = path.join(htmlDir, f);
  let s = fs.readFileSync(fp, "utf8");
  const next = s.replace(re, `$1${ver}`);
  if (next !== s) {
    fs.writeFileSync(fp, next, "utf8");
    changed++;
    console.log("updated", f);
  }
}
if (!changed) console.log("no car-page script ?v= matches in frontend/*.html");
