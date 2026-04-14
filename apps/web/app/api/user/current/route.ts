import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth";

export async function GET() {
  try {
    const user = await getCurrentUser();

    if (!user) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    return NextResponse.json({
      id: user.id,
      email: user.email,
      name: user.name,
      creditsBalance: user.creditsBalance,
    });
  } catch (error) {
    console.error("[/api/user/current] Error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
