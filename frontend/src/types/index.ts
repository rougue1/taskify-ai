// Shared TypeScript types for Taskify. These mirror the backend Pydantic
// schemas (see backend/app/schemas) so the API contract stays in sync.

export type TaskStatus = "todo" | "in_progress" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface Task {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  tags: string[];
  due_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateTaskInput {
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  tags?: string[] | null;
  due_date?: string | null;
}

export interface UpdateTaskInput {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  tags?: string[] | null;
  due_date?: string | null;
}

export type TaskSortField =
  | "created_at"
  | "updated_at"
  | "due_date"
  | "priority"
  | "title";
export type SortOrder = "asc" | "desc";

export interface TaskFilters {
  status?: TaskStatus;
  priority?: TaskPriority;
}

export interface TaskQuery extends TaskFilters {
  sort_by?: TaskSortField;
  sort_order?: SortOrder;
  page?: number;
  page_size?: number;
}

export interface PaginatedTasks {
  items: Task[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  id?: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  tool_calls?: ToolCall[];
  // Map of tool call id -> result text, filled as tool_end events arrive.
  toolOutputs?: Record<string, string>;
  reasoning?: string;
  // Transient UI state used while an assistant message is streaming.
  streaming?: boolean;
}

export interface AgentResponse {
  response: string;
  tool_calls: ToolCall[];
  tokens_used: number;
  session_id: string;
}

// --- Auth --------------------------------------------------------------------

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// --- Streaming events (SSE from /agent/stream) -------------------------------

export interface ToolEvent {
  name: string;
  args?: Record<string, unknown>;
  id?: string | null;
  output?: string;
}

export interface StreamHandlers {
  onSession?: (sessionId: string) => void;
  onThinking?: (text: string) => void;
  onToken?: (text: string) => void;
  onToolStart?: (tool: ToolEvent) => void;
  onToolEnd?: (tool: ToolEvent) => void;
  onDone?: (data: AgentResponse) => void;
  onError?: (message: string) => void;
}

// --- Display helpers ---------------------------------------------------------

export const TASK_STATUSES: TaskStatus[] = ["todo", "in_progress", "done"];
export const TASK_PRIORITIES: TaskPriority[] = [
  "low",
  "medium",
  "high",
  "urgent",
];

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "To Do",
  in_progress: "In Progress",
  done: "Done",
};

export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

export const SORT_FIELD_LABELS: Record<TaskSortField, string> = {
  created_at: "Created",
  updated_at: "Updated",
  due_date: "Due date",
  priority: "Priority",
  title: "Title",
};
