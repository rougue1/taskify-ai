// Typed API client. All task/agent/auth calls hit relative `/api/v1/*` paths,
// which Next.js rewrites to the FastAPI backend (see next.config.ts). The health
// check goes through the local Next.js route handler at `/api/health`.
//
// Every authenticated request attaches the Bearer access token and transparently
// refreshes it once on a 401; if refresh fails the auth store is cleared (the
// protected route then redirects to /login).

import { useAuthStore } from "@/store/authStore";
import type {
  AgentResponse,
  CreateTaskInput,
  PaginatedTasks,
  Task,
  TaskQuery,
  TokenPair,
  StreamHandlers,
  UpdateTaskInput,
  User,
} from "@/types";

const API_BASE = "/api/v1";
// SSE goes through a dedicated Route Handler (not the buffering rewrite proxy)
// so events stream to the browser incrementally.
const STREAM_PATH = "/api/agent/stream";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function authHeader(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(response: Response): Promise<ApiError> {
  let message = response.statusText;
  let code: string | undefined;
  try {
    const body = await response.json();
    message = body?.error?.message ?? body?.detail ?? body?.message ?? message;
    code = body?.error?.code;
  } catch {
    // no JSON body — keep the status text
  }
  return new ApiError(message, response.status, code);
}

// --- Token refresh (deduplicated across concurrent 401s) ---------------------

let refreshInFlight: Promise<boolean> | null = null;

async function refreshOnce(): Promise<boolean> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) return false;
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) {
      useAuthStore.getState().clearAuth();
      return false;
    }
    const tokens = (await response.json()) as TokenPair;
    useAuthStore.getState().setTokens(tokens);
    return true;
  } catch {
    useAuthStore.getState().clearAuth();
    return false;
  }
}

function attemptRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = refreshOnce().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeader(),
      ...(options.headers ?? {}),
    },
  });

  if (response.status === 401 && retry) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      return request<T>(path, options, false);
    }
  }

  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// --- Auth --------------------------------------------------------------------

export async function registerRequest(
  email: string,
  password: string,
): Promise<TokenPair> {
  const response = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as TokenPair;
}

export async function loginRequest(
  email: string,
  password: string,
): Promise<TokenPair> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as TokenPair;
}

export async function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

// --- Tasks -------------------------------------------------------------------

export async function getTasks(query: TaskQuery = {}): Promise<PaginatedTasks> {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.priority) params.set("priority", query.priority);
  if (query.sort_by) params.set("sort_by", query.sort_by);
  if (query.sort_order) params.set("sort_order", query.sort_order);
  if (query.page) params.set("page", String(query.page));
  if (query.page_size) params.set("page_size", String(query.page_size));
  const qs = params.toString();
  return request<PaginatedTasks>(`/tasks${qs ? `?${qs}` : ""}`);
}

export async function createTask(input: CreateTaskInput): Promise<Task> {
  return request<Task>("/tasks", { method: "POST", body: JSON.stringify(input) });
}

export async function updateTask(
  id: number,
  input: UpdateTaskInput,
): Promise<Task> {
  return request<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function deleteTask(id: number): Promise<void> {
  await request<void>(`/tasks/${id}`, { method: "DELETE" });
}

// --- Agent (non-streaming, kept alongside the SSE stream) --------------------

export async function sendMessage(
  message: string,
  sessionId: string | null,
): Promise<AgentResponse> {
  return request<AgentResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId }),
  });
}

// --- Agent (SSE streaming) ---------------------------------------------------

function dispatchFrame(frame: string, handlers: StreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(dataLines.join("\n"));
  } catch {
    return;
  }
  switch (event) {
    case "session":
      handlers.onSession?.(data.session_id as string);
      break;
    case "thinking":
      handlers.onThinking?.((data.content as string) ?? "");
      break;
    case "token":
      handlers.onToken?.((data.content as string) ?? "");
      break;
    case "tool_start":
      handlers.onToolStart?.(data as never);
      break;
    case "tool_end":
      handlers.onToolEnd?.(data as never);
      break;
    case "done":
      handlers.onDone?.(data as unknown as AgentResponse);
      break;
    case "error":
      handlers.onError?.((data.message as string) ?? "Agent error");
      break;
  }
}

export async function streamMessage(
  message: string,
  sessionId: string | null,
  handlers: StreamHandlers,
  signal: AbortSignal,
  retry = true,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(STREAM_PATH, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ message, session_id: sessionId }),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    handlers.onError?.("Could not reach the assistant.");
    return;
  }

  if (response.status === 401 && retry) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      return streamMessage(message, sessionId, handlers, signal, false);
    }
    handlers.onError?.("Your session expired. Please log in again.");
    return;
  }
  if (!response.ok || !response.body) {
    const error = await parseError(response);
    handlers.onError?.(error.message);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let separator = buffer.indexOf("\n\n");
      while (separator !== -1) {
        const frame = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        dispatchFrame(frame, handlers);
        separator = buffer.indexOf("\n\n");
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      handlers.onError?.((err as Error).message);
    }
  }
}

// --- Health ------------------------------------------------------------------

export async function healthCheck(): Promise<{ status: string }> {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    if (!response.ok) {
      return { status: "disconnected" };
    }
    return (await response.json()) as { status: string };
  } catch {
    return { status: "disconnected" };
  }
}
