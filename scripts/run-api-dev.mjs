#!/usr/bin/env node
/**
 * Run API (FastAPI) at apps/api. Uses Python 3.11 venv or py -3.11.
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
const venvSitePackages = path.join(apiDir, isWin ? ".venv/Lib/site-packages" : ".venv/lib/python3.11/site-packages");

// On Windows, venv is often broken if project was moved. Use system Python + PYTHONPATH so API starts without recreating venv.
const useVenv = fs.existsSync(venvPy) && (!isWin || process.env.USE_API_VENV === "1");

// Use minimal requirements for faster local dev (GPU work happens on AWS SageMaker)
const useMinimal = process.env.USE_MINIMAL_REQUIREMENTS !== "false";
const requirementsFile = useMinimal && fs.existsSync(path.join(apiDir, "requirements-minimal.txt"))
  ? "requirements-minimal.txt"
  : "requirements.txt";

let py = venvPy;
let pipPy = venvPy;
let pipArgs = [];
let uvicornArgs = [];

// ai-pipeline dir is at repo root — needs explicit --reload-dir so uvicorn hot-reloads it
const aiPipelineDir = path.join(root, "ai-pipeline");

// Add ai-pipeline to PYTHONPATH so `from services.xxx import ...` works in the API
const existingPythonPath = process.env.PYTHONPATH || "";
const pythonPathParts = existingPythonPath ? existingPythonPath.split(path.delimiter) : [];
if (!pythonPathParts.includes(aiPipelineDir)) pythonPathParts.unshift(aiPipelineDir);
let env = { ...process.env, PYTHONPATH: pythonPathParts.join(path.delimiter) };

// Load .env.local into process env so API keys are available even when uvicorn
// doesn't support --env-file (older versions) — read the file ourselves and inject.
const envLocalPath = path.join(apiDir, ".env.local");
if (fs.existsSync(envLocalPath)) {
  const lines = fs.readFileSync(envLocalPath, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const k = trimmed.slice(0, eq).trim();
    const v = trimmed.slice(eq + 1).trim().replace(/^['"]|['"]$/g, "");
    if (k && !(k in env)) env[k] = v; // don't override shell env
  }
  console.log("[run-api-dev] Loaded .env.local into API process environment");
}

if (useVenv) {
  pipArgs = ["-m", "pip", "install", "-r", requirementsFile, "-q", "--no-warn-script-location", "--default-timeout=100", "--retries=3"];
  uvicornArgs = ["-m", "uvicorn", "app.main:app", "--reload",
    "--reload-dir", apiDir,
    "--reload-dir", aiPipelineDir,
    "--host", "127.0.0.1", "--port", "8003",
    "--loop", "asyncio"];   // uvloop unavailable on Windows; bypasses auto_loop_setup removed in uvicorn 0.30+
} else {
  py = isWin ? "py" : "python3.11";
  const pyVer = isWin ? ["-3.11"] : [];
  pipPy = py;
  pipArgs = [...pyVer, "-m", "pip", "install", "-r", requirementsFile, "-q", "--no-warn-script-location", "--default-timeout=100", "--retries=3"];
  uvicornArgs = [...pyVer, "-m", "uvicorn", "app.main:app", "--reload",
    "--reload-dir", apiDir,
    "--reload-dir", aiPipelineDir,
    "--host", "127.0.0.1", "--port", "8003",
    "--loop", "asyncio"];   // uvloop unavailable on Windows; bypasses auto_loop_setup removed in uvicorn 0.30+
  if (isWin && fs.existsSync(venvSitePackages)) {
    env.PYTHONPATH = venvSitePackages;
    // Only use --target if path has no space (shell would split "PhotoGenius AI" and break pip)
    if (!venvSitePackages.includes(" ")) {
      pipArgs = [...pipArgs, "--target", venvSitePackages];
    }
  }
}

// shell: true is needed for `py -3.11` pip install on Windows.
// shell: false is REQUIRED for uvicorn — paths with spaces (e.g. "PhotoGenius AI")
//   are passed as-is in the args array when shell=false, avoiding shell word-splitting.
const pipOpts  = { cwd: apiDir, stdio: "inherit", env, shell: isWin && pipPy === "py" };
const uvicornOpts = { cwd: apiDir, stdio: "inherit", env, shell: false };

// ── Skip pip install if requirements haven't changed ─────────────────────────
// pip's post-install conflict checker reads ALL system packages and causes a
// MemoryError on large installs (pip bug). Avoid by caching requirements hash.
import { createHash } from "crypto";
const reqPath    = path.join(apiDir, requirementsFile);
const hashFile   = path.join(apiDir, `.pip-hash-${requirementsFile.replace(/[^a-z0-9]/gi, "_")}`);
const reqContent = fs.existsSync(reqPath) ? fs.readFileSync(reqPath, "utf8") : "";
const reqHash    = createHash("sha1").update(reqContent).digest("hex");
const cachedHash = fs.existsSync(hashFile) ? fs.readFileSync(hashFile, "utf8").trim() : "";
const needsInstall = reqHash !== cachedHash || process.env.FORCE_PIP_INSTALL === "1";

if (!needsInstall) {
  console.log(`[run-api-dev] Python deps up-to-date (${requirementsFile} unchanged) — skipping pip`);
} else {
  console.log(`[run-api-dev] Installing Python deps from ${requirementsFile}…`);
  if (useMinimal && requirementsFile === "requirements-minimal.txt") {
    console.log("[run-api-dev] Using minimal requirements (GPU work happens on AWS SageMaker)");
    console.log("[run-api-dev] To install full requirements: USE_MINIMAL_REQUIREMENTS=false pnpm run dev");
  }

  const pip = spawnSync(pipPy, pipArgs, pipOpts);
  if (pip.status !== 0) {
    console.warn("[run-api-dev] ⚠️  pip installation had issues, but continuing...");
    console.warn("[run-api-dev] FastAPI should still work. If not, install manually:");
    console.warn(`[run-api-dev]   cd apps/api && ${pipPy} -m pip install -r ${requirementsFile}`);
    // Don't exit - let uvicorn try to start anyway
  } else {
    // Save hash so we skip next time
    fs.writeFileSync(hashFile, reqHash, "utf8");
  }
}

// ── Kill any existing process on port 8003 before starting ────────────────
const API_PORT = 8003;
console.log(`[run-api-dev] Freeing port ${API_PORT}…`);
if (isWin) {
  // Windows: netstat → extract PID → taskkill
  const netstat = spawnSync("cmd", ["/c", `for /f "tokens=5" %a in ('netstat -ano ^| findstr ":${API_PORT} "') do taskkill /F /PID %a`],
    { stdio: "pipe", shell: false });
  if (netstat.stdout?.toString().includes("SUCCESS")) {
    console.log(`[run-api-dev] Killed old process on port ${API_PORT}`);
  }
} else {
  // Unix: fuser or lsof
  spawnSync("sh", ["-c", `fuser -k ${API_PORT}/tcp 2>/dev/null || lsof -ti:${API_PORT} | xargs kill -9 2>/dev/null`],
    { stdio: "pipe" });
}

console.log("[run-api-dev] Starting uvicorn…");
const uvicorn = spawnSync(py, uvicornArgs, uvicornOpts);
process.exit(uvicorn.status ?? 0);
