import { NextRequest, NextResponse } from "next/server";

export function GET(req: NextRequest) {
  const base = req.nextUrl.origin;
  return NextResponse.redirect(new URL("/dashboard", base));
}
