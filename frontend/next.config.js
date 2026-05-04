/** @type {import('next').NextConfig} */
//
// Rewrites proxy /api/* and /health from the Next.js dev server to the FastAPI
// backend. Browser sees same-origin requests (localhost:3000 → localhost:3000),
// Next.js forwards them to the backend behind the scenes. Avoids CORS
// complications and lets pages use plain relative URLs ("/api/foo").
//
// Backend default port is 8000 (matches `uvicorn ... --port 8000`).
// Override per-environment via NEXT_PUBLIC_API_URL in .env.local.
//
const BACKEND = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/health", destination: `${BACKEND}/health` },
    ];
  },
};

module.exports = nextConfig;
