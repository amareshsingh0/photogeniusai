/**
 * POST /api/generate/stream
 *
 * SSE proxy: forwards the FastAPI streaming generation endpoint to the browser,
 * intercepting `final_ready` to save the generation to DB and inject generationId.
 */
import { auth } from "@/lib/auth";
import { cookies } from "next/headers";
import { prisma, isPrismaDbUnavailable } from "@/lib/db";

export const dynamic = "force-dynamic";
export const maxDuration = 120; // 2 min — fal.ai fast/standard well within this

const MODE_MAP: Record<string, string> = {
  photorealism:          "REALISM",
  artistic:              "ARTISTIC",
  character_consistency: "REALISM",
  interior_arch:         "REALISM",
  editing:               "REALISM",
  typography:            "CREATIVE",
  vector:                "CREATIVE",
  fast:                  "REALISM",
};

const CREDITS_MAP: Record<string, number> = {
  ultra: 3, quality: 3, balanced: 2, fast: 1,
};

export async function POST(req: Request) {
  await cookies(); // ensure dynamic context

  const body = await req.json() as {
    prompt?: string;
    quality?: string;
    style?: string;
    width?: number;
    height?: number;
    reference_image?: string;
    negative_prompt?: string;
  };

  const {
    prompt,
    quality = "balanced",
    style,
    width = 1024,
    height = 1024,
    reference_image,
    negative_prompt,
  } = body;

  if (!prompt || prompt.trim().length < 3) {
    return Response.json({ error: "Prompt must be at least 3 characters" }, { status: 400 });
  }

  const apiBase =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8003";

  // Get auth early — can't await inside ReadableStream
  let clerkId: string | null = null;
  try {
    const session = await auth();
    clerkId = session?.userId ?? null;
  } catch {}

  const creditsUsed = CREDITS_MAP[quality] ?? 2;

  // Connect to FastAPI SSE endpoint
  let backendRes: Response;
  try {
    backendRes = await fetch(`${apiBase}/api/v1/generate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: prompt.trim(),
        quality,
        style,
        width,
        height,
        reference_image_url: reference_image,
        negative_prompt,
      }),
    });
  } catch {
    return Response.json({ error: "AI backend is not reachable" }, { status: 503 });
  }

  if (!backendRes.ok || !backendRes.body) {
    return Response.json({ error: `Backend error ${backendRes.status}` }, { status: 502 });
  }

  const upstreamReader = backendRes.body.getReader();
  const decoder = new TextDecoder();
  const encoder = new TextEncoder();

  // Transform stream: pass through all events, intercept final_ready to add generationId
  const stream = new ReadableStream({
    async start(controller) {
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await upstreamReader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE messages are separated by double newlines
          const messages = buffer.split("\n\n");
          buffer = messages.pop() ?? ""; // keep incomplete tail

          for (const msg of messages) {
            if (!msg.trim()) continue;

            const eventMatch = msg.match(/^event:\s*(\w+)/m);
            const dataMatch = msg.match(/^data:\s*(.+)/m);

            if (eventMatch?.[1] === "final_ready" && dataMatch) {
              // Intercept: save to DB and re-emit with generationId
              try {
                const data = JSON.parse(dataMatch[1]);
                let generationId: string | undefined;

                if (clerkId && data.image_url) {
                  try {
                    const dbUser = await prisma.user.upsert({
                      where: { clerkId },
                      create: {
                        clerkId,
                        email: `${clerkId}@photogenius.local`,
                        creditsBalance: 1000,
                      },
                      update: {},
                      select: { id: true },
                    });
                    const gen = await prisma.generation.create({
                      data: {
                        userId: dbUser.id,
                        originalPrompt: prompt.trim(),
                        mode: (MODE_MAP[data.capability_bucket ?? ""] ?? "REALISM") as "REALISM" | "CREATIVE" | "ARTISTIC",
                        outputUrls: data.all_urls?.length ? data.all_urls : [data.image_url],
                        selectedOutputUrl: data.image_url,
                        postGenSafetyPassed: true,
                        isDeleted: false,
                        creditsUsed,
                        qualityTierUsed: quality,
                        aestheticScore: null,
                      },
                    });
                    generationId = gen.id;
                    await prisma.user
                      .update({
                        where: { id: dbUser.id },
                        data: { creditsBalance: { decrement: creditsUsed } },
                      })
                      .catch(() => {});
                  } catch (dbErr) {
                    if (!isPrismaDbUnavailable(dbErr)) {
                      console.error("[stream/route] DB save failed:", dbErr);
                    }
                  }
                }

                const enhanced = { ...data, generationId };
                controller.enqueue(
                  encoder.encode(`event: final_ready\ndata: ${JSON.stringify(enhanced)}\n\n`)
                );
              } catch {
                // JSON parse failed — pass raw through
                controller.enqueue(encoder.encode(`${msg}\n\n`));
              }
            } else {
              controller.enqueue(encoder.encode(`${msg}\n\n`));
            }
          }
        }
      } catch (err) {
        console.error("[stream/route] stream error:", err);
        controller.enqueue(
          encoder.encode(
            `event: error\ndata: ${JSON.stringify({ message: "Stream error" })}\n\n`
          )
        );
      } finally {
        controller.close();
      }
    },
    cancel() {
      upstreamReader.cancel();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
