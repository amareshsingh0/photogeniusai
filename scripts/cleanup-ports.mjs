#!/usr/bin/env node
/**
 * Kill stale processes on dev ports before starting.
 * Prevents port conflicts that cause the app to pick wrong ports.
 */
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";

const PORTS = [3002, 8000, 8001];

if (isWin) {
  for (const port of PORTS) {
    try {
      const out = execSync(`netstat -ano | findstr ":${port} " | findstr "LISTENING"`, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "pipe"],
      });
      const pids = new Set();
      for (const line of out.trim().split("\n")) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && /^\d+$/.test(pid) && Number(pid) > 0) pids.add(pid);
      }
      for (const pid of pids) {
        try {
          execSync(`taskkill /F /PID ${pid}`, { stdio: "ignore" });
          console.log(`[cleanup] Killed PID ${pid} on port ${port}`);
        } catch (_) {}
      }
    } catch (_) {
      // No process on this port - good
    }
  }
} else {
  for (const port of PORTS) {
    try {
      execSync(`lsof -ti :${port} | xargs kill -9 2>/dev/null`, { stdio: "ignore" });
      console.log(`[cleanup] Killed process on port ${port}`);
    } catch (_) {}
  }
}

// Clean stale port files
for (const f of [".api-port", ".web-url", ".serve-home-port"]) {
  try {
    fs.unlinkSync(path.join(root, f));
  } catch (_) {}
}

console.log("[cleanup] Ports cleared, ready to start dev server");
