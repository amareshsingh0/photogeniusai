#!/usr/bin/env node
/**
 * Run Next.js web app on a FIXED port 3002.
 * If port 3002 is busy, kills the process holding it first, then starts fresh.
 * Use 127.0.0.1 to avoid Windows IPv6 localhost issues.
 */
import { spawn, execSync } from "child_process";
import net from "net";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const webDir = path.join(root, "apps", "web");

const HOST = "127.0.0.1";
const PORT = 3002;
const URL = `http://${HOST}:${PORT}`;

function isPortAvailable(host, port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => { server.close(); resolve(true); });
    server.listen(port, host);
  });
}

function killPortWindows(port) {
  try {
    // Find PIDs listening on the port
    const out = execSync(`netstat -ano`, { encoding: "utf8" });
    const pids = new Set();
    for (const line of out.split("\n")) {
      // Match lines like: TCP  127.0.0.1:3002  ... LISTENING  1234
      if (line.includes(`:${port}`) && (line.includes("LISTENING") || line.includes("ESTABLISHED"))) {
        const parts = line.trim().split(/\s+/);
        const pid = parseInt(parts[parts.length - 1], 10);
        if (pid > 4) pids.add(pid); // skip System (PID 4)
      }
    }
    for (const pid of pids) {
      try {
        execSync(`taskkill /PID ${pid} /F`, { stdio: "ignore" });
        console.log(`[run-web-dev] Killed PID ${pid} (was holding port ${port})`);
      } catch { /* already gone */ }
    }
  } catch { /* netstat not available or no match */ }
}

// Ensure port 3002 is free — kill any process holding it
if (!(await isPortAvailable(HOST, PORT))) {
  console.log(`[run-web-dev] Port ${PORT} is busy — killing process…`);
  killPortWindows(PORT);
  // Wait up to 3s for port to release
  for (let i = 0; i < 6; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isPortAvailable(HOST, PORT)) break;
  }
  if (!(await isPortAvailable(HOST, PORT))) {
    console.error(`[run-web-dev] Could not free port ${PORT}. Kill it manually and retry.`);
    process.exit(1);
  }
  console.log(`[run-web-dev] Port ${PORT} is now free.`);
}

function isPortOpen(host, port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    const onError = () => { socket.destroy(); resolve(false); };
    socket.setTimeout(500);
    socket.once("error", onError);
    socket.once("timeout", onError);
    socket.connect(port, host, () => { socket.destroy(); resolve(true); });
  });
}

console.log("[run-web-dev] Starting Next.js on " + URL + " …");
// Next.js compiles 1000+ modules — default ~1.5 GB heap OOMs on large projects.
// 4 GB gives ample room for dev compilation + hot reload.
// NODE_OPTIONS env var on Windows shell=true is unreliable; pass heap flag directly
// via `node --max-old-space-size` so it reaches the webpack worker process.
const NODE_HEAP = process.env.NODE_HEAP_MB ?? "4096";

// Clear stale .next/cache on every start — prevents RangeError after OOM crashes
// where webpack cache pack files are left in a corrupted half-written state.
const nextCacheDir = path.join(webDir, ".next", "cache");
if (fs.existsSync(nextCacheDir)) {
  fs.rmSync(nextCacheDir, { recursive: true, force: true });
  console.log("[run-web-dev] Cleared stale .next/cache (fresh webpack compilation)");
}

const child = spawn(
  "node",
  [`--max-old-space-size=${NODE_HEAP}`, "node_modules/.bin/next", "dev", "-p", String(PORT), "-H", HOST],
  {
    cwd: webDir,
    stdio: "inherit",
    shell: false,   // shell:false so paths with spaces are passed verbatim
    env: { ...process.env, FORCE_COLOR: "1" },
  }
);

let readyLogged = false;
const check = async () => {
  if (readyLogged) return;
  if (await isPortOpen(HOST, PORT)) {
    readyLogged = true;
    console.log("\n[run-web-dev] Ready: " + URL + " — open this in your browser.\n");
  }
};

// Poll until port is open (after a short delay so Next can start)
setTimeout(() => {
  const interval = setInterval(async () => {
    await check();
    if (readyLogged) clearInterval(interval);
  }, 800);
  // Also clear after 2 min so we don't poll forever
  setTimeout(() => clearInterval(interval), 120000);
}, 2000);

child.on("exit", (code, signal) => {
  process.exit(code ?? (signal ? 1 : 0));
});

process.on("SIGINT", () => child.kill("SIGINT"));
process.on("SIGTERM", () => child.kill("SIGTERM"));
