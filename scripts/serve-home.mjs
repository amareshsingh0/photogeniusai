#!/usr/bin/env node
/**
 * Standalone server — sirf start.html serve karta hai. Next.js bypass.
 * Auto-picks free port 3099, 3098, ... 3080.
 */
import http from "http";
import net from "net";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const __root = path.join(__dirname, "..");
const publicDir = path.join(__root, "apps", "web", "public");
const HOST = "127.0.0.1";
const startFile = path.join(publicDir, "start.html");

function getWebUrl() {
  try {
    const webUrlPath = path.join(__root, ".web-url");
    if (fs.existsSync(webUrlPath)) return fs.readFileSync(webUrlPath, "utf8").trim();
  } catch (_) {}
  return "http://127.0.0.1:3002";
}

function getHtml() {
  const webUrl = getWebUrl();
  let html = fs.existsSync(startFile)
    ? fs.readFileSync(startFile, "utf8")
    : `<html><body style="margin:0;padding:40px;background:#0d0d0d;color:#fff"><h1>PhotoGenius AI</h1><p>Home</p></body></html>`;
  return html.replace(/__WEB_APP_URL__/g, webUrl);
}

function isPortFree(port) {
  return new Promise((resolve) => {
    const s = net.createServer();
    s.once("error", () => resolve(false));
    s.once("listening", () => {
      s.close();
      resolve(true);
    });
    s.listen(port, HOST);
  });
}

async function findPort() {
  for (let p = 3099; p >= 3080; p--) {
    if (await isPortFree(p)) return p;
  }
  return 3099;
}

const server = http.createServer((req, res) => {
  const html = getHtml();
  res.writeHead(200, {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store, no-cache, must-revalidate",
  });
  res.end(html);
});

const port = await findPort();
server.listen(port, HOST, () => {
  const url = "http://" + HOST + ":" + port;
  try {
    fs.writeFileSync(path.join(__root, ".serve-home-port"), String(port), "utf8");
  } catch (_) {}
  console.log("\n[serve-home] Page chal raha hai: " + url);
  console.log("[serve-home] Browser mein YAHI URL copy karke kholo.\n");
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.error("[serve-home] Port " + port + " busy. Koi process band karo ya dobara chalao.");
  }
  process.exit(1);
});
