import type { Metadata, Viewport } from "next";
import { Fraunces, Inter, JetBrains_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteNav, MobileDock } from "@/components/pixium/site-nav";
import { ConditionalFooter } from "@/components/pixium/conditional-footer";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fraunces",
  weight: ["400", "500", "600", "700", "800"],
});

const geist = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Pixium Studio",
  description: "Advanced AI image generation engine",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Pixium",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"),
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "Pixium",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0d0d0d",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${fraunces.variable} ${geist.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-screen w-full overflow-x-hidden bg-background font-sans text-foreground antialiased">
        <a href="#main" className="skip-link">Skip to content</a>
        <Providers>
          <SiteNav />
          <main id="main" tabIndex={-1} className="relative z-10 pt-20 focus:outline-none">
            {children}
          </main>
          <ConditionalFooter />
          <MobileDock />
        </Providers>
      </body>
    </html>
  );
}
