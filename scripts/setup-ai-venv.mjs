#!/usr/bin/env node
/**
 * Create Python 3.11 venv in apps/ai-service and install requirements.
 * Run once after cloning. Then use npm run dev:ai (or npm run dev).
 */
import { spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const aiDir = path.join(root, "apps", "ai-service");
const isWin = process.platform === "win32";
const venvDir = path.join(aiDir, ".venv");
const venvPy = path.join(venvDir, isWin ? "Scripts/python.exe" : "bin/python");
const venvPip = path.join(venvDir, isWin ? "Scripts/pip.exe" : "bin/pip");

const py = isWin ? "py" : "python3.11";
const pyVer = isWin ? ["-3.11"] : [];

console.log("[setup:ai] Creating venv with Python 3.11…");
const venv = spawnSync(py, [...pyVer, "-m", "venv", venvDir], {
  cwd: aiDir,
  stdio: "inherit",
  shell: isWin,
});
if (venv.status !== 0) {
  console.error("[setup:ai] venv failed. Install Python 3.11: https://www.python.org/downloads/");
  process.exit(venv.status ?? 1);
}

if (!fs.existsSync(venvPip)) {
  console.error("[setup:ai] pip not found in venv.");
  process.exit(1);
}

console.log("[setup:ai] Installing requirements.txt…");
const pip = spawnSync(venvPip, ["install", "-r", "requirements.txt", "-q", "--no-warn-script-location"], {
  cwd: aiDir,
  stdio: "inherit",
});
if (pip.status !== 0) {
  process.exit(pip.status ?? 1);
}

console.log("[setup:ai] Done. Run npm run dev (or npm run dev:ai).");
