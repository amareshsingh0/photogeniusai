#!/usr/bin/env node
/**
 * Run API tests (pytest). Uses apps/api .venv if present.
 */
import { spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const apiDir = path.join(root, "apps", "api");
const isWin = process.platform === "win32";
const venvPy = path.join(apiDir, isWin ? ".venv/Scripts/python.exe" : ".venv/bin/python");

let py = venvPy;
let pipPy = venvPy;
const pyVer = isWin ? ["-3.11"] : [];

if (!fs.existsSync(venvPy)) {
  py = isWin ? "py" : "python3.11";
  pipPy = py;

  // Check if Python is actually available; if not, skip gracefully (e.g. CI without Python)
  const check = spawnSync(pipPy, isWin ? ["-3.11", "--version"] : ["--version"], {
    cwd: apiDir,
    stdio: "pipe",
    shell: isWin,
  });
  if (check.status !== 0) {
    console.log("[run-api-test] Python not available – skipping API tests (run pytest directly)");
    process.exit(0);
  }
}

const opts = { cwd: apiDir, stdio: "inherit", env: process.env };
if (isWin && (py === "py" || pipPy === "py")) opts.shell = true;

const pipArgsBase = ["-m", "pip", "install", "-q", "--no-warn-script-location"];
const pipArgsPy = [...pyVer, ...pipArgsBase];
console.log("[run-api-test] Installing deps…");
for (const req of ["requirements.txt", "requirements-dev.txt"]) {
  const arg = fs.existsSync(venvPy) ? [...pipArgsBase, "-r", req] : [...pipArgsPy, "-r", req];
  const pip = spawnSync(pipPy, arg, opts);
  if (pip.status !== 0) {
    console.error("[run-api-test] pip install -r " + req + " failed");
    process.exit(pip.status ?? 1);
  }
}

console.log("[run-api-test] Running pytest…");
const args = process.argv.slice(2);
const pytest = spawnSync(py, fs.existsSync(venvPy) ? ["-m", "pytest", ...args] : [...pyVer, "-m", "pytest", ...args], opts);
process.exit(pytest.status ?? 0);
