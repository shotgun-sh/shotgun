import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0f2240",
};

export const metadata: Metadata = {
  title: "Shotgun — Intelligent Specs, Not Templates",
  description:
    "Shotgun analyzes your codebase, researches existing solutions, and generates specs that keep your AI agent on track. Start free with BYOK.",
  keywords: [
    "spec-driven development",
    "AI coding agent",
    "codebase analysis",
    "intelligent specs",
    "Cursor",
    "Claude Code",
    "Windsurf",
    "BYOK",
    "multi-agent orchestration",
  ],
  authors: [{ name: "Shotgun" }],
  creator: "Shotgun",
  metadataBase: new URL("https://shotgun.sh"),
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Shotgun — Intelligent Specs, Not Templates",
    description:
      "Research before building. Ship faster. Stop reinventing wheels. Shotgun generates contextual specs from your codebase.",
    type: "website",
    url: "https://shotgun.sh",
    siteName: "Shotgun",
    locale: "en_US",
    images: [
      {
        url: "/images/og-image.png",
        width: 1200,
        height: 630,
        alt: "Shotgun — Intelligent Specs, Not Templates. Analyze your codebase, research solutions, generate specs.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Shotgun — Intelligent Specs, Not Templates",
    description:
      "Analyze your codebase. Research solutions. Generate specs. Keep your AI agent on track.",
    images: ["/images/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {/* Skip to main content link for keyboard navigation */}
        <a
          href="#main-content"
          className="
            sr-only focus:not-sr-only
            focus:fixed focus:top-4 focus:left-4 focus:z-50
            focus:rounded-[var(--radius-md)]
            focus:bg-primary focus:text-text-inverse
            focus:px-[var(--space-4)] focus:py-[var(--space-2)]
            focus:text-[length:var(--font-size-sm)]
            focus:font-[var(--font-weight-semibold)]
            focus:outline-2 focus:outline-offset-2 focus:outline-[var(--color-accent)]
          "
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
