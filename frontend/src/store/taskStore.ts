// Zustand store for task and chat state. Centralizes all client state so any
// component can read tasks/chat and dispatch actions without prop drilling.

import { create } from "zustand";

import * as api from "@/lib/api";
import type {
  ChatMessage,
  CreateTaskInput,
  Task,
  TaskFilters,
  UpdateTaskInput,
} from "@/types";

interface TaskState {
  // Task state
  tasks: Task[];
  isLoading: boolean;
  error: string | null;
  filters: TaskFilters;

  // Chat state
  chatHistory: ChatMessage[];
  isChatLoading: boolean;
  chatError: string | null;

  // Task actions
  setFilters: (filters: TaskFilters) => void;
  fetchTasks: () => Promise<void>;
  createTask: (input: CreateTaskInput) => Promise<void>;
  updateTask: (id: number, input: UpdateTaskInput) => Promise<void>;
  deleteTask: (id: number) => Promise<void>;

  // Chat actions
  sendChatMessage: (message: string) => Promise<void>;
  clearChat: () => void;
}

function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  isLoading: false,
  error: null,
  filters: {},

  chatHistory: [],
  isChatLoading: false,
  chatError: null,

  setFilters: (filters) => {
    set({ filters });
    void get().fetchTasks();
  },

  fetchTasks: async () => {
    set({ isLoading: true, error: null });
    try {
      const tasks = await api.getTasks(get().filters);
      set({ tasks, isLoading: false });
    } catch (error) {
      set({ error: toMessage(error), isLoading: false });
    }
  },

  createTask: async (input) => {
    try {
      await api.createTask(input);
      await get().fetchTasks();
    } catch (error) {
      set({ error: toMessage(error) });
      throw error;
    }
  },

  updateTask: async (id, input) => {
    try {
      const updated = await api.updateTask(id, input);
      set({
        tasks: get().tasks.map((task) => (task.id === id ? updated : task)),
      });
    } catch (error) {
      set({ error: toMessage(error) });
      throw error;
    }
  },

  deleteTask: async (id) => {
    const previous = get().tasks;
    // Optimistic removal; restore on failure.
    set({ tasks: previous.filter((task) => task.id !== id) });
    try {
      await api.deleteTask(id);
    } catch (error) {
      set({ tasks: previous, error: toMessage(error) });
      throw error;
    }
  },

  sendChatMessage: async (message) => {
    const userMessage: ChatMessage = { role: "user", content: message };
    const history = get().chatHistory;
    set({
      chatHistory: [...history, userMessage],
      isChatLoading: true,
      chatError: null,
    });

    try {
      // TODO v0.4: replace fetch with SSE streaming
      const result = await api.sendMessage(message, history);
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: result.response,
        tool_calls: result.tool_calls,
      };
      set({
        chatHistory: [...get().chatHistory, assistantMessage],
        isChatLoading: false,
      });

      // The agent may have created/updated tasks via tool calls — refresh.
      if (result.tool_calls?.length) {
        void get().fetchTasks();
      }
    } catch (error) {
      set({
        isChatLoading: false,
        chatError: toMessage(error),
        chatHistory: [
          ...get().chatHistory,
          {
            role: "assistant",
            content:
              "Sorry, I could not reach the assistant. Please make sure the backend and Ollama are running.",
          },
        ],
      });
    }
  },

  clearChat: () => set({ chatHistory: [], chatError: null }),
}));
