import type { Metadata, Viewport } from "next";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "PhotoGenius AI",
  description: "AI-powered portrait studio with Instant Magic Preview",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "PhotoGenius",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"),
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "PhotoGenius AI",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#3b82f6",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className="min-h-screen w-full overflow-x-hidden bg-background font-sans text-foreground antialiased"
        style={{ backgroundColor: "#0d0d0d", fontFamily: "system-ui, -apple-system, sans-serif" }}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
