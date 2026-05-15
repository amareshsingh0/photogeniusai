import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Allowlist of upstream origins we'll proxy. Anything else returns 400.
const ALLOWED_HOSTS = [
  "v3.fal.media",
  "v2.fal.media",
  "fal.media",
  "fal.run",
  "fal.ai",
  "storage.googleapis.com",     // some fal storage uses GCS
  "fal.cdn.something",           // future-proofing aliases via env
];

const ALLOWED_HOST_SUFFIXES = [
  ".fal.media",
  ".fal.ai",
  ".fal.run",
  ".amazonaws.com",  // our S3 bucket — still proxied so URLs stay Pixium-branded
];

function isHostAllowed(host: string): boolean {
  if (ALLOWED_HOSTS.includes(host)) return true;
  return ALLOWED_HOST_SUFFIXES.some((s) => host.endsWith(s));
}

/**
 * GET /api/img/<base64url-of-upstream-url>
 *   OR
 * GET /api/img/fal/<path>   (e.g. /api/img/fal/files/xxx/abc.png)
 * GET /api/img/s3/<path>    (e.g. /api/img/s3/generations/xxx.png)
 *
 * Proxies the upstream image so the visible URL stays under
 * creatives.bimoraai.com — no fal.media / amazonaws.com domains leak to the user.
 */
export async function GET(
  req: Request,
  ctx: { params: { path: string[] } }
) {
  const parts = ctx.params.path || [];
  if (parts.length === 0) return NextResponse.json({ error: "missing path" }, { status: 400 });

  let upstreamUrl: string;

  // Path style 1: /api/img/p/<rest>   → https://v3.fal.media/<rest>     (p = "provider", was "fal")
  // Path style 2: /api/img/c/<rest>   → https://<S3_HOST>/<rest>         (c = "cache",    was "s3")
  // Path style 3: /api/img/<base64url> → decoded URL (any allowed host)
  // Legacy aliases /api/img/fal/* and /api/img/s3/* are still accepted so existing
  // links / DB-stored URLs don't break.
  if (parts[0] === "p" || parts[0] === "fal") {
    upstreamUrl = `https://v3.fal.media/${parts.slice(1).join("/")}`;
  } else if (parts[0] === "c" || parts[0] === "s3") {
    const s3Host = process.env.S3_PUBLIC_HOST
      || `${process.env.S3_BUCKET_NAME || "pixium-images-288761732313-ap-south-1-an"}.s3.${process.env.S3_REGION || "ap-south-1"}.amazonaws.com`;
    upstreamUrl = `https://${s3Host}/${parts.slice(1).join("/")}`;
  } else {
    // Base64-url-encoded full URL
    try {
      const b64 = parts.join("/");
      const decoded = Buffer.from(b64, "base64url").toString("utf8");
      const u = new URL(decoded);
      if (!isHostAllowed(u.hostname)) {
        return NextResponse.json({ error: "host not allowed", host: u.hostname }, { status: 400 });
      }
      upstreamUrl = decoded;
    } catch {
      return NextResponse.json({ error: "bad upstream encoding" }, { status: 400 });
    }
  }

  // Re-validate host (path style 1 and 2 build it ourselves; verify anyway)
  try {
    const u = new URL(upstreamUrl);
    if (!isHostAllowed(u.hostname)) {
      return NextResponse.json({ error: "host not allowed", host: u.hostname }, { status: 400 });
    }
  } catch {
    return NextResponse.json({ error: "bad url" }, { status: 400 });
  }

  const upstream = await fetch(upstreamUrl, {
    headers: {
      // Mimic a browser; some CDNs reject default Node fetch UA
      "User-Agent": "Mozilla/5.0 (PixiumImageProxy)",
      "Accept": "image/*",
    },
    // Stream the response straight through — no buffering full image in memory
    cache: "no-store",
  });

  if (!upstream.ok) {
    return NextResponse.json(
      { error: "upstream failed", status: upstream.status },
      { status: upstream.status }
    );
  }

  const ct = upstream.headers.get("content-type") || "image/png";
  const cl = upstream.headers.get("content-length") || undefined;

  // Stream the body to the client; long-cache (1 year) since image URLs include
  // content hashes / UUIDs and never change.
  const headers: Record<string, string> = {
    "Content-Type": ct,
    "Cache-Control": "public, max-age=31536000, immutable",
  };
  if (cl) headers["Content-Length"] = cl;

  return new NextResponse(upstream.body, { status: 200, headers });
}
