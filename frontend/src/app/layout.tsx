import type { Metadata, Viewport } from "next";

import "./globals.css";

import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "AI Pulse", template: "%s · AI Pulse" },
  description: "AI & technology intelligence: models, research, tools, bugs, CVEs and cloud incidents — with sources.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a1020" },
    { media: "(prefers-color-scheme: light)", color: "#f6f7fb" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
