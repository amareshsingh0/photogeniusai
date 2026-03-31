import { NextResponse } from 'next/server'

// Clerk webhooks disabled - using custom auth
export async function POST(req: Request) {
  return NextResponse.json({ ok: true, message: 'Clerk webhooks disabled' })
}
