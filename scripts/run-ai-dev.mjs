#!/usr/bin/env node
/**
 * Run AI service (FastAPI) with Python 3.11.
 * Prefers apps/ai-service/.venv if present; otherwise uses py -3.11 (Windows) or python3.11 (Unix).
 * Node 18–20 LTS required. Do not use Node 24.
 */
import { spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const aiDir = path.join(root, "apps", "ai-service");
const isWin = process.platform === "win32";
const venvPy = path.join(aiDir, isWin ? ".venv/Scripts/python.exe" : ".venv/bin/python");

let py = venvPy;
let pipPy = venvPy;
let pipArgs = [];
let uvicornArgs = [];

if (fs.existsSync(venvPy)) {
  pipArgs = ["-m", "pip", "install", "-r", "requirements.txt", "-q", "--no-warn-script-location"];
  uvicornArgs = ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001"];
} else {
  py = isWin ? "py" : "python3.11";
  const pyVer = isWin ? ["-3.11"] : [];
  pipPy = py;
  pipArgs = [...pyVer, "-m", "pip", "install", "-r", "requirements.txt", "-q", "--no-warn-script-location"];
  uvicornArgs = [...pyVer, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001"];
}

const opts = { cwd: aiDir, stdio: "inherit", env: process.env };
if (isWin && (py === "py" || pipPy === "py")) {
  opts.shell = true;
}

console.log("[run-ai-dev] Installing Python deps…");
const pip = spawnSync(pipPy, pipArgs, opts);
if (pip.status !== 0) {
  console.error("[run-ai-dev] Python deps failed. Install Python 3.11 and run: npm run setup:ai");
  process.exit(pip.status ?? 1);
}

console.log("[run-ai-dev] Starting uvicorn…");
const uvicorn = spawnSync(py, uvicornArgs, opts);
process.exit(uvicorn.status ?? 0);
