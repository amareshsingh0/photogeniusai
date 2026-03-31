/**
 * Next.js Instrumentation Hook
 * https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 *
 * Problem: Node.js undici (used by global `fetch`) has a default headersTimeout of 300s.
 * The AI generation backend (FastAPI) can take up to 550s for PREMIUM tier.
 * When a concurrent request holds the GPU lock, the second request waits behind it —
 * the GPU lock queue cascade makes headers arrive after 300s, triggering
 * UND_ERR_HEADERS_TIMEOUT before the AbortSignal.timeout(600_000) fires.
 *
 * Fix: Increase undici Agent headersTimeout + bodyTimeout to 900s on server startup.
 * This covers: PREMIUM async inference (≈550s) + GPU queue wait (≈120s) + margin.
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    try {
      // Use dynamic import path that webpack won't try to resolve at compile time
      const undiciPath = "undici";
      const { setGlobalDispatcher, Agent } = await import(
        /* webpackIgnore: true */ undiciPath
      );
      setGlobalDispatcher(
        new Agent({
          headersTimeout: 900_000, // 900s -- covers PREMIUM queue cascade
          bodyTimeout:    900_000, // 900s -- covers large base64 image response
          connectTimeout: 10_000,  // 10s  -- fail fast on connection refused
        })
      );
      console.log("[PhotoGenius] undici headersTimeout/bodyTimeout -> 900s (PREMIUM AI support)");
    } catch {
      // Non-fatal: undici may not be available; AbortSignal.timeout(600_000) is the fallback
    }
  }
}
