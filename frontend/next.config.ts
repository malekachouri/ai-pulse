import type { NextConfig } from "next";

// The browser only ever talks to this Next.js origin; /api/v1 is proxied to FastAPI server-side.
// Note: rewrites are resolved at build time — set BACKEND_URL when running `next build`.
// This keeps the httpOnly refresh cookie first-party and means no API URL or key is shipped to clients.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const securityHeaders = [
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
