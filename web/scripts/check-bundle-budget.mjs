/**
 * Проверка gzip-размеров client chunks после `next build`.
 * Пороги в bundle-budget.json — при превышении exit 1 (CI).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const chunksDir = join(root, ".next", "static", "chunks");
const budgetPath = join(root, "bundle-budget.json");

const budget = JSON.parse(readFileSync(budgetPath, "utf-8"));

function gzipSize(filePath) {
  const buf = readFileSync(filePath);
  return gzipSync(buf).length;
}

function walkJs(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walkJs(p));
    else if (name.endsWith(".js")) out.push(p);
  }
  return out;
}

if (!statSync(chunksDir, { throwIfNoEntry: false })) {
  console.error("[bundle-budget] Run `npm run build` in web/ first (.next/static/chunks missing).");
  process.exit(1);
}

const files = walkJs(chunksDir);
let totalGzip = 0;
let maxChunk = { name: "", bytes: 0 };
let frameworkGzip = 0;

for (const file of files) {
  const gz = gzipSize(file);
  totalGzip += gz;
  const base = file.split(/[/\\]/).pop() ?? file;
  if (gz > maxChunk.bytes) maxChunk = { name: base, bytes: gz };
  if (/^framework-.*\.js$/i.test(base)) frameworkGzip += gz;
}

const failures = [];
if (totalGzip > budget.maxTotalClientGzipBytes) {
  failures.push(
    `total client gzip ${totalGzip} > ${budget.maxTotalClientGzipBytes} (${(totalGzip / 1024).toFixed(0)} KiB)`,
  );
}
if (maxChunk.bytes > budget.maxSingleChunkGzipBytes) {
  failures.push(
    `largest chunk ${maxChunk.name} gzip ${maxChunk.bytes} > ${budget.maxSingleChunkGzipBytes}`,
  );
}
if (
  budget.maxFrameworkChunkGzipBytes &&
  frameworkGzip > budget.maxFrameworkChunkGzipBytes
) {
  failures.push(
    `framework chunks gzip ${frameworkGzip} > ${budget.maxFrameworkChunkGzipBytes}`,
  );
}

console.log(
  `[bundle-budget] ${files.length} chunks, total gzip ${(totalGzip / 1024).toFixed(1)} KiB, ` +
    `framework ${(frameworkGzip / 1024).toFixed(1)} KiB, max ${maxChunk.name} ${(maxChunk.bytes / 1024).toFixed(1)} KiB`,
);

if (failures.length) {
  console.error("[bundle-budget] FAILED:\n" + failures.map((f) => `  - ${f}`).join("\n"));
  process.exit(1);
}

console.log("[bundle-budget] OK");
