import { NextResponse } from "next/server";
import { appendFileSync, mkdirSync } from "fs";
import { join } from "path";

export async function POST(req: Request) {
  try {
    const payload = (await req.json()) as Record<string, unknown>;
    const line =
      JSON.stringify({ ...payload, timestamp: payload.timestamp ?? Date.now() }) + "\n";
    const cwd = process.cwd();
    const nextPath = join(cwd, ".next", "debug.log");
    const cursorDir = join(cwd, "..", "..", ".cursor");
    const cursorPath = join(cursorDir, "debug.log");
    try {
      appendFileSync(nextPath, line);
    } catch (_) {}
    try {
      mkdirSync(cursorDir, { recursive: true });
      appendFileSync(cursorPath, line);
    } catch (_) {}
  } catch (_) {}
  return new Response(null, { status: 204 });
}

