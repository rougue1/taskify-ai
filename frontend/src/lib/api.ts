// Typed API client. All task/agent calls hit relative `/api/v1/*` paths, which
// Next.js rewrites to the FastAPI backend (see next.config.ts). The health
// check goes through the local Next.js route handler at `/api/health`.

import type {
  AgentResponse,
  ChatMessage,
  CreateTaskInput,
  Task,
  TaskFilters,
  UpdateTaskInput,
} from "@/types";

const API_BASE = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? body.message ?? detail;
    } catch {
      // response had no JSON body; keep the status text
    }
    throw new Error(`API ${response.status}: ${detail}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function getTasks(filters?: TaskFilters): Promise<Task[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.priority) params.set("priority", filters.priority);
  const query = params.toString();
  return request<Task[]>(`/tasks${query ? `?${query}` : ""}`);
}

export async function getTask(id: number): Promise<Task> {
  return request<Task>(`/tasks/${id}`);
}

export async function createTask(input: CreateTaskInput): Promise<Task> {
  return request<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify(input),
  });
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

export async function sendMessage(
  message: string,
  history: ChatMessage[],
): Promise<AgentResponse> {
  return request<AgentResponse>("/agent/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

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
