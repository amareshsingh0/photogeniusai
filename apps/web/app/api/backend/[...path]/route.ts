import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

/**
 * Proxy route for FastAPI backend.
 * All requests to /api/backend/* are forwarded to FASTAPI_URL/api/*
 * 
 * This handles the main API endpoints including:
 * - /api/v1/generation/* - Image generation
 * - /api/v1/identities/* - Identity management
 */

// Force dynamic rendering - this route uses headers via Clerk auth
export const dynamic = 'force-dynamic';

const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

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

export async function PATCH(req: NextRequest, { params }: { params: { path: string[] } }) {
  return proxyRequest(req, params.path, "PATCH");
}

async function proxyRequest(req: NextRequest, pathSegments: string[], method: string) {
  const path = pathSegments.join("/");
  const url = `${FASTAPI_URL}/api/${path}`;

  // Get auth info - pass through to backend, let FastAPI handle authorization
  let userId: string | null = null;
  let token: string | null = null;

  try {
    const authResult = await auth();
    userId = authResult.userId;
    token = await authResult.getToken();
  } catch (e) {
    console.log("[Backend Proxy] Auth info not available, passing request through");
  }

  const headers: Record<string, string> = {};
  req.headers.forEach((value, key) => {
    if (!["host", "connection", "content-length"].includes(key.toLowerCase())) {
      headers[key] = value;
    }
  });

  // Add authorization header if we have a token
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  
  // Also pass user ID in a custom header for backend use
  if (userId) {
    headers["X-User-Id"] = userId;
  }

  const body = method !== "GET" && method !== "HEAD" ? await req.text() : undefined;

  try {
    console.log(`[Backend Proxy] ${method} ${url} (user: ${userId || 'anonymous'})`);
    
    const response = await fetch(url, { 
      method, 
      headers, 
      body,
      // Increase timeout for generation requests (sync can take 10+ minutes)
      signal: AbortSignal.timeout(path.includes("generation") ? 660000 : 120000), // 11 min for generation, 2 min for others
    });
    
    const data = await response.text();

    return new NextResponse(data, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
    });
  } catch (error) {
    console.error("[Backend Proxy] Error:", error);
    
    if (error instanceof Error && error.name === 'TimeoutError') {
      return NextResponse.json({ error: "Request timeout" }, { status: 504 });
    }
    
    return NextResponse.json({ error: "Backend service unavailable" }, { status: 503 });
  }
}
