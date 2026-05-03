/** @type {import('next').NextConfig} */
// Note: Environment validation happens in lib/env.ts when imported
// This file uses process.env directly as Next.js handles env loading

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  // Stable build ID — prevents "Failed to find Server Action 'x'" errors when
  // stale browser tabs from a prior deployment ping the new server. Falls back
  // to a timestamp if the git hash isn't available at build time.
  generateBuildId: async () => {
    try {
      const { execSync } = require("child_process");
      return execSync("git rev-parse HEAD").toString().trim().slice(0, 12);
    } catch {
      return `build-${Date.now()}`;
    }
  },
  // Performance optimizations
  compress: true,
  poweredByHeader: false,
  // Optimize images
  images: {
    formats: ["image/avif", "image/webp"],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    minimumCacheTTL: 60,
    remotePatterns: [
      // S3 generic + regional path-style endpoints (ap-south-1 etc).
      { protocol: "https", hostname: "**.s3.amazonaws.com" },
      { protocol: "https", hostname: "**.s3.*.amazonaws.com" },
      { protocol: "https", hostname: "**.amazonaws.com" },
      { protocol: "https", hostname: "**.r2.cloudflarestorage.com" },
      { protocol: "https", hostname: "**.supabase.co" },
      // fal.ai delivery (used for non-S3 fallback)
      { protocol: "https", hostname: "**.fal.media" },
      { protocol: "https", hostname: "v3.fal.media" },
      { protocol: "https", hostname: "fal.media" },
      // WaveSpeed CDN (returned when wan_2_7 / hunyuan finish)
      { protocol: "https", hostname: "**.cloudfront.net" },
      // Google generated content (Imagen sometimes returns gstatic)
      { protocol: "https", hostname: "**.googleusercontent.com" },
      { protocol: "https", hostname: "**.gstatic.com" },
      { protocol: "https", hostname: "picsum.photos" },
    ],
  },
  // Optimize bundle
  experimental: {
    instrumentationHook: true, // enables instrumentation.ts (undici timeout fix for PREMIUM)
    optimizePackageImports: [
      "lucide-react",
      "framer-motion",
      "@radix-ui/react-dialog",
      "@radix-ui/react-dropdown-menu",
      "@radix-ui/react-slot",
      "@tanstack/react-query",
      "zod",
      "recharts",
    ],
  },
  // Webpack optimizations
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // Optimize chunk splitting
      config.optimization = {
        ...config.optimization,
        moduleIds: "deterministic",
        runtimeChunk: "single",
      };
    }
    return config;
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL,
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL,
  },
};

module.exports = nextConfig;
