/**
 * E2E: Next dev with virtual catalog list enabled.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const web = path.join(__dirname, "..", "web");

const child = spawn("npm run dev -- --port 24174 --hostname 127.0.0.1", {
  cwd: web,
  stdio: ["ignore", "inherit", "inherit"],
  shell: true,
  env: {
    ...process.env,
    NEXT_PUBLIC_API_BASE: "http://127.0.0.1:28765",
    WRA_API_INTERNAL: "http://127.0.0.1:28765",
    NEXT_PUBLIC_FEATURE_VIRTUAL_LIST: "1",
  },
});

function shutdown() {
  try {
    child.kill("SIGTERM");
  } catch {
    // ignore
  }
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
child.on("exit", (code) => process.exit(code ?? 0));
process.stdin.resume();
