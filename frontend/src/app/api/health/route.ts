import { NextResponse } from "next/server";

// Server-side health check. Proxies to the FastAPI backend's /health endpoint
// so the browser can poll connectivity without CORS and without knowing the
// backend URL. Returns { status: "disconnected" } when the backend is down.

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });

    if (!response.ok) {
      return NextResponse.json({ status: "disconnected" }, { status: 503 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ status: "disconnected" }, { status: 503 });
  }
}
