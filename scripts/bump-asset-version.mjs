#!/usr/bin/env node
/**
 * Заменить суффикс ?v=... у car-page-dicts.js и car-page.js в статических HTML (web/public).
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

const base = path.join(root, "web", "public");
const files = [];

function walk(dir) {
  if (!fs.existsSync(dir)) return;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p);
    else if (ent.name.endsWith(".html")) files.push(p);
  }
}
walk(base);

const re = /(car-page(?:-dicts)?\.js\?v=)([^"'&\s]+)/g;
let changed = 0;
for (const fp of files) {
  let s = fs.readFileSync(fp, "utf8");
  const next = s.replace(re, `$1${ver}`);
  if (next !== s) {
    fs.writeFileSync(fp, next, "utf8");
    changed++;
    console.log("updated", path.relative(root, fp));
  }
}
if (!changed) console.log("no car-page script ?v= matches in web/public/**/*.html");
