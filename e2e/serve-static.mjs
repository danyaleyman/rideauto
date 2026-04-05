/**
 * E2E: отдать frontend/ по HTTP :4173 (для Playwright webServer).
 */
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const py =
  process.env.PYTHON ||
  (process.platform === "win32" ? "python" : "python3");

const child = spawn(py, ["-m", "http.server", "24173"], {
  cwd: path.join(root, "frontend"),
  stdio: ["ignore", "inherit", "inherit"],
  env: { ...process.env },
});

function shutdown() {
  try {
    child.kill("SIGTERM");
  } catch {
    /* ignore */
  }
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
child.on("exit", (code) => process.exit(code ?? 0));
process.stdin.resume();
