/**
 * E2E: run Next dev server on :24173 against mock API.
 */
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const web = path.join(root, "web");

const command =
  process.platform === "win32"
    ? "npm run dev -- --port 24173 --hostname 127.0.0.1"
    : "npm run dev -- --port 24173 --hostname 127.0.0.1";

const child = spawn(command, {
  cwd: web,
  stdio: ["ignore", "inherit", "inherit"],
  shell: true,
  env: {
    ...process.env,
    NEXT_PUBLIC_API_BASE: "http://127.0.0.1:28765",
    WRA_API_INTERNAL: "http://127.0.0.1:28765",
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
