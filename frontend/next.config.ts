import type { NextConfig } from "next";

// The browser only ever talks to this Next.js origin; /api/v1 is proxied to FastAPI server-side.
// Note: rewrites are resolved at build time — set BACKEND_URL when running `next build`.
// This keeps the httpOnly refresh cookie first-party and means no API URL or key is shipped to clients.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const dev = process.env.NODE_ENV === "development";
// Next.js app-router pages bootstrap with inline scripts, so script-src needs 'unsafe-inline' (no per-request
// nonces). The policy still blocks third-party scripts, framing, plugins, <base> hijacking and foreign form
// posts. Dev adds what React Refresh and HMR need. Images may come from any HTTPS host (e.g. avatars).
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws: wss:" : ""}`,
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default config;
