import type { NextConfig } from "next";

// Base URL of the FastAPI backend. Override via BACKEND_URL in the environment
// (see .env.local.example) for non-default setups or Docker (v0.8).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Proxy all versioned API calls to the backend so the browser only ever talks
  // to the Next.js origin (no CORS in the browser, backend URL stays private).
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
