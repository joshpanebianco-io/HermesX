// Run a tool from the server venv, so `npm run py:lint` works from the repo
// root without anyone having to know where the venv lives or activate it.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const server = join(root, "server");
const py = join(server, ".venv", "Scripts", "python.exe");

if (!existsSync(py)) {
  console.error("No venv at server/.venv — run .\server\run.ps1 once to create it.");
  process.exit(1);
}

const [tool, ...rest] = process.argv.slice(2);
if (!tool) {
  console.error("usage: node scripts/py.mjs <tool> [args...]");
  process.exit(1);
}

const r = spawnSync(py, ["-m", tool, ...rest], { cwd: server, stdio: "inherit" });
process.exit(r.status ?? 1);
