/**
 * E2E: подготовить БД и поднять api_server на :8765 (для Playwright webServer).
 */
import { execFileSync, spawn } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const db = path.resolve(root, "e2e", "fixtures", "catalog-e2e.db");
const py =
  process.env.PYTHON ||
  (process.platform === "win32" ? "python" : "python3");

fs.mkdirSync(path.dirname(db), { recursive: true });
execFileSync(
  py,
  [path.join(root, "e2e", "scripts", "init_e2e_db.py"), db],
  { stdio: "inherit", cwd: root },
);

const child = spawn(
  py,
  ["-m", "api_server", "--db", db, "--host", "127.0.0.1", "--port", "28765"],
  {
    cwd: path.join(root, "backend"),
    stdio: ["ignore", "inherit", "inherit"],
    env: { ...process.env },
  },
);

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
