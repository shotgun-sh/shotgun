import type { Metadata } from "next";
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

export const metadata: Metadata = {
  title: "Shotgun — Intelligent Specs, Not Templates",
  description:
    "Shotgun analyzes your codebase, researches existing solutions, and generates specs that keep your AI agent on track. Start free with BYOK.",
  openGraph: {
    title: "Shotgun — Intelligent Specs, Not Templates",
    description:
      "Research before building. Ship faster. Stop reinventing wheels. Shotgun generates contextual specs from your codebase.",
    type: "website",
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
        {children}
      </body>
    </html>
  );
}
