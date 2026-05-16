/**
 * Image URL branding — rewrites third-party image URLs (fal.media, S3) to our
 * own /api/img/* proxy route so the visible domain stays creatives.bimoraai.com.
 * No fal / amazonaws domain leaks to the user-visible HTML.
 *
 * Pass any image URL through `brandedImageUrl(url)` before rendering.
 * data:, blob:, /api/img/* and already-local paths are returned unchanged.
 */

const FAL_HOSTS_SUFFIX = [".fal.media", ".fal.ai", ".fal.run"];
const FAL_HOSTS_EXACT  = ["fal.media", "fal.ai", "fal.run"];

// The image-proxy routes (`/api/img/p/*`, `/api/img/c/*`) live on the Next.js
// web host only. When this code runs on a page served from a different host
// (e.g. the admin panel mounted at api.creatives.bimoraai.com/admin), a bare
// `/api/img/...` path resolves to the API host — which has no such route and
// returns 404. Detect that case and emit an absolute URL pointing to the web
// host so the proxy is always reachable.
function proxyOrigin(): string {
  if (typeof window === "undefined") return ""; // SSR: relative is fine
  const appUrl = process.env.NEXT_PUBLIC_APP_URL;
  if (!appUrl) return "";
  try {
    const webHost = new URL(appUrl).host;
    if (window.location.host !== webHost) {
      return new URL(appUrl).origin;
    }
  } catch { /* malformed env — fall through to relative */ }
  return "";
}

function isFalUrl(u: URL): boolean {
  if (FAL_HOSTS_EXACT.includes(u.hostname)) return true;
  return FAL_HOSTS_SUFFIX.some((s) => u.hostname.endsWith(s));
}

function isS3Url(u: URL): boolean {
  return u.hostname.endsWith(".amazonaws.com");
}

export function brandedImageUrl(src: string | undefined | null): string {
  if (!src) return "";

  // Pass-through cases — already local or non-URL forms
  if (src.startsWith("data:") || src.startsWith("blob:")) return src;
  if (src.startsWith("/")) return src;
  if (!src.startsWith("http")) return src;

  let u: URL;
  try {
    u = new URL(src);
  } catch {
    return src;
  }

  const origin = proxyOrigin();

  // fal.media URLs → /api/img/p/<path...>   (p = "provider", obfuscated to hide upstream brand)
  if (isFalUrl(u)) {
    const path = u.pathname.replace(/^\/+/, "");
    const qs = u.search ? u.search : "";
    return `${origin}/api/img/p/${path}${qs}`;
  }

  // S3 URLs → /api/img/c/<path...>          (c = "cache", obfuscated to hide AWS brand)
  if (isS3Url(u)) {
    const path = u.pathname.replace(/^\/+/, "");
    const qs = u.search ? u.search : "";
    return `${origin}/api/img/c/${path}${qs}`;
  }

  // Anything else (already-CDN or third-party) — leave as-is
  return src;
}
