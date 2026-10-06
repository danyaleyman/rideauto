#!/usr/bin/env node
/** Fail if en.json / ru.json key sets diverge. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");

function flatten(obj, prefix = "", out = new Set()) {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    out.add(prefix);
    return out;
  }
  for (const [k, v] of Object.entries(obj)) {
    const p = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === "object" && !Array.isArray(v)) flatten(v, p, out);
    else out.add(p);
  }
  return out;
}

const ru = JSON.parse(fs.readFileSync(path.join(root, "messages/ru.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(root, "messages/en.json"), "utf8"));
const ruKeys = flatten(ru);
const enKeys = flatten(en);
const missingInEn = [...ruKeys].filter((k) => !enKeys.has(k)).sort();
const missingInRu = [...enKeys].filter((k) => !ruKeys.has(k)).sort();
console.log(`ru keys=${ruKeys.size} en keys=${enKeys.size}`);
if (missingInEn.length) {
  console.error("Missing in en.json:", missingInEn.slice(0, 50).join("\n"));
}
if (missingInRu.length) {
  console.error("Missing in ru.json:", missingInRu.slice(0, 50).join("\n"));
}
if (missingInEn.length || missingInRu.length) process.exit(2);
console.log("i18n key parity OK");
