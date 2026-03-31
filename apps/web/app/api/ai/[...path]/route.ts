import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy route for AI service (SDXL generation).
 * All requests to /api/ai/* are forwarded to AI_SERVICE_URL/api/*
 */

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://127.0.0.1:8001";

export async function GET(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path, "GET");
}

export async function POST(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path, "POST");
}

export async function PUT(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path, "PUT");
}

export async function DELETE(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path, "DELETE");
}

async function proxyRequest(req: NextRequest, pathSegments: string[], method: string) {
  const path = pathSegments.join("/");
  const url = `${AI_SERVICE_URL}/api/${path}`;

  const headers: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    if (!["host", "connection", "content-length"].includes(key.toLowerCase())) {
      headers[key] = value;
    }
  });

  const body = method !== "GET" && method !== "HEAD" ? await req.text() : undefined;

  try {
    const response = await fetch(url, { method, headers, body });
    const data = await response.text();

    return new NextResponse(data, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
    });
  } catch (error) {
    console.error("AI Proxy error:", error);
    return NextResponse.json({ error: "AI service unavailable" }, { status: 503 });
  }
}
