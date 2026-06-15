import { NextRequest } from "next/server";

// Streaming proxy for the agent SSE endpoint.
//
// Next.js `rewrites()` buffer proxied streaming responses, which would collapse
// the whole token/thinking stream into a single burst at the end. This Route
// Handler instead pipes the backend's response body straight through, so SSE
// events reach the browser as they are produced. The browser still only talks
// to the Next.js origin (no CORS, backend URL stays private).

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const authorization = req.headers.get("authorization");

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/api/v1/agent/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
      },
      body,
    });
  } catch {
    return new Response(
      JSON.stringify({ error: { code: "bad_gateway", message: "Backend unreachable." } }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  // Pass non-OK responses (e.g. 401) through untouched so the client can react.
  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
