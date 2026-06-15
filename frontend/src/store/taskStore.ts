// Zustand store for task and chat state. Centralizes all client state so any
// component can read tasks/chat and dispatch actions without prop drilling.
//
// Mutations are optimistic (instant UI, rolled back on error) and every one
// raises a toast. Chat streams over SSE: tokens, reasoning and tool calls land
// on the in-progress assistant message as events arrive.

import { toast } from "sonner";
import { create } from "zustand";

import * as api from "@/lib/api";
import type {
  ChatMessage,
  CreateTaskInput,
  SortOrder,
  Task,
  TaskFilters,
  TaskSortField,
  UpdateTaskInput,
} from "@/types";

const PAGE_SIZE = 12;

interface TaskState {
  // Task state
  tasks: Task[];
  isLoading: boolean;
  error: string | null;
  filters: TaskFilters;
  sortBy: TaskSortField;
  sortOrder: SortOrder;
  page: number;
  pages: number;
  total: number;

  // Chat state
  chatHistory: ChatMessage[];
  isChatLoading: boolean;
  chatError: string | null;
  sessionId: string | null;
  chatAbort: AbortController | null;

  // Task actions
  setFilters: (filters: TaskFilters) => void;
  setSort: (sortBy: TaskSortField, sortOrder: SortOrder) => void;
  setPage: (page: number) => void;
  fetchTasks: () => Promise<void>;
  createTask: (input: CreateTaskInput) => Promise<void>;
  updateTask: (id: number, input: UpdateTaskInput) => Promise<void>;
  deleteTask: (id: number) => Promise<void>;

  // Chat actions
  sendChatMessage: (message: string) => Promise<void>;
  stopStreaming: () => void;
  newConversation: () => void;
}

function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  isLoading: false,
  error: null,
  filters: {},
  sortBy: "created_at",
  sortOrder: "desc",
  page: 1,
  pages: 1,
  total: 0,

  chatHistory: [],
  isChatLoading: false,
  chatError: null,
  sessionId: null,
  chatAbort: null,

  setFilters: (filters) => {
    set({ filters, page: 1 });
    void get().fetchTasks();
  },

  setSort: (sortBy, sortOrder) => {
    set({ sortBy, sortOrder, page: 1 });
    void get().fetchTasks();
  },

  setPage: (page) => {
    set({ page });
    void get().fetchTasks();
  },

  fetchTasks: async () => {
    set({ isLoading: true, error: null });
    try {
      const { filters, sortBy, sortOrder, page } = get();
      const res = await api.getTasks({
        ...filters,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: PAGE_SIZE,
      });
      set({
        tasks: res.items,
        total: res.total,
        pages: Math.max(1, res.pages),
        page: res.page,
        isLoading: false,
      });
    } catch (error) {
      set({ error: toMessage(error), isLoading: false });
    }
  },

  createTask: async (input) => {
    const tempId = -Date.now();
    const now = new Date().toISOString();
    const optimistic: Task = {
      id: tempId,
      user_id: 0,
      title: input.title,
      description: input.description ?? null,
      status: input.status ?? "todo",
      priority: input.priority ?? "medium",
      tags: input.tags ?? [],
      due_date: input.due_date ?? null,
      created_at: now,
      updated_at: now,
    };
    set((s) => ({ tasks: [optimistic, ...s.tasks], total: s.total + 1 }));
    try {
      const created = await api.createTask(input);
      set((s) => ({ tasks: s.tasks.map((t) => (t.id === tempId ? created : t)) }));
      toast.success("Task created");
      void get().fetchTasks();
    } catch (error) {
      set((s) => ({
        tasks: s.tasks.filter((t) => t.id !== tempId),
        total: Math.max(0, s.total - 1),
        error: toMessage(error),
      }));
      toast.error(`Could not create task: ${toMessage(error)}`);
      throw error;
    }
  },

  updateTask: async (id, input) => {
    const previous = get().tasks;
    // Optimistically apply the change; reconcile with the server's version next.
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === id ? ({ ...t, ...input, tags: input.tags ?? t.tags } as Task) : t,
      ),
    }));
    try {
      const updated = await api.updateTask(id, input);
      set((s) => ({ tasks: s.tasks.map((t) => (t.id === id ? updated : t)) }));
      toast.success("Task updated");
    } catch (error) {
      set({ tasks: previous, error: toMessage(error) });
      toast.error(`Could not update task: ${toMessage(error)}`);
      throw error;
    }
  },

  deleteTask: async (id) => {
    const previous = get().tasks;
    const previousTotal = get().total;
    set((s) => ({
      tasks: s.tasks.filter((t) => t.id !== id),
      total: Math.max(0, s.total - 1),
    }));
    try {
      await api.deleteTask(id);
      toast.success("Task deleted");
    } catch (error) {
      set({ tasks: previous, total: previousTotal, error: toMessage(error) });
      toast.error(`Could not delete task: ${toMessage(error)}`);
      throw error;
    }
  },

  sendChatMessage: async (message) => {
    const userMessage: ChatMessage = { role: "user", content: message };
    const assistantMessage: ChatMessage = {
      role: "assistant",
      content: "",
      reasoning: "",
      tool_calls: [],
      toolOutputs: {},
      streaming: true,
    };
    set((s) => ({
      chatHistory: [...s.chatHistory, userMessage, assistantMessage],
      isChatLoading: true,
      chatError: null,
    }));

    const assistantIndex = get().chatHistory.length - 1;
    const controller = new AbortController();
    set({ chatAbort: controller });

    const patchAssistant = (patch: (m: ChatMessage) => ChatMessage) =>
      set((s) => {
        const history = s.chatHistory.slice();
        const current = history[assistantIndex];
        if (current && current.role === "assistant") {
          history[assistantIndex] = patch(current);
        }
        return { chatHistory: history };
      });

    let toolRan = false;

    await api.streamMessage(
      message,
      get().sessionId,
      {
        onSession: (sessionId) => set({ sessionId }),
        onThinking: (text) =>
          patchAssistant((m) => ({ ...m, reasoning: (m.reasoning ?? "") + text })),
        onToken: (text) => patchAssistant((m) => ({ ...m, content: m.content + text })),
        onToolStart: (tool) => {
          toolRan = true;
          patchAssistant((m) => ({
            ...m,
            tool_calls: [
              ...(m.tool_calls ?? []),
              { name: tool.name, args: tool.args ?? {}, id: tool.id },
            ],
          }));
        },
        onToolEnd: (tool) =>
          patchAssistant((m) => ({
            ...m,
            toolOutputs: {
              ...(m.toolOutputs ?? {}),
              [tool.id ?? tool.name]: tool.output ?? "",
            },
          })),
        onDone: (data) => {
          patchAssistant((m) => ({
            ...m,
            content: data.response || m.content,
            tool_calls: data.tool_calls?.length ? data.tool_calls : m.tool_calls,
            streaming: false,
          }));
        },
        onError: (msg) => {
          patchAssistant((m) => ({
            ...m,
            content:
              m.content ||
              "Sorry, I could not reach the assistant. Please make sure the backend and Ollama are running.",
            streaming: false,
          }));
          set({ chatError: msg });
          toast.error(msg);
        },
      },
      controller.signal,
    );

    patchAssistant((m) => ({ ...m, streaming: false }));
    set({ isChatLoading: false, chatAbort: null });

    // The agent may have created/updated tasks via tool calls — refresh.
    if (toolRan) {
      void get().fetchTasks();
    }
  },

  stopStreaming: () => {
    const controller = get().chatAbort;
    if (controller) {
      controller.abort();
    }
    set((s) => ({
      isChatLoading: false,
      chatAbort: null,
      chatHistory: s.chatHistory.map((m) =>
        m.streaming ? { ...m, streaming: false } : m,
      ),
    }));
  },

  newConversation: () => {
    get().chatAbort?.abort();
    set({
      chatHistory: [],
      chatError: null,
      sessionId: null,
      isChatLoading: false,
      chatAbort: null,
    });
  },
}));
