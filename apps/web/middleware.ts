import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const HEADER = "x-request-id"

/**
 * Middleware - adds request ID + blocks admin on web domain
 * Excludes ALL API routes to avoid interference
 */
export default function middleware(req: NextRequest) {
  const url = req.nextUrl.clone()
  const host = req.headers.get("host") || ""

  // SECURITY: Block /admin access on web domain (users should NEVER see admin on main site)
  if (url.pathname.startsWith("/admin") && host.includes("creatives.bimoraai.com") && !host.includes("api.")) {
    // Return 404 - don't redirect to API domain
    return NextResponse.rewrite(new URL("/not-found", req.url), { status: 404 })
  }

  // Add request ID
  const id = req.headers.get(HEADER) ?? req.headers.get("X-Request-ID") ?? crypto.randomUUID()
  const response = NextResponse.next()
  response.headers.set(HEADER, String(id).slice(0, 64))
  return response
}

export const config = {
  // Only run on page routes, exclude ALL api routes
  matcher: [
    "/((?!api|_next/static|_next/image|favicon\\.ico|manifest\\.json|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|json|woff2?)$).*)"
  ],
}
