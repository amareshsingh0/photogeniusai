import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const HEADER = "x-request-id"

/** 
 * Minimal middleware - just adds request ID
 * Excludes ALL API routes to avoid interference
 */
export default function middleware(req: NextRequest) {
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
