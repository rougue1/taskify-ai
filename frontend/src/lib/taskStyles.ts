// Shared visual tokens + formatters for tasks, used by the Kanban board and the
// task detail panel so colors and date formatting stay consistent. All classes
// include dark-mode variants.

import type { TaskPriority, TaskStatus } from "@/types";

// Color-coded priority badges: urgent=red, high=orange, medium=yellow, low=green.
export const PRIORITY_BADGE: Record<TaskPriority, string> = {
  low: "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300",
  medium:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-500/20 dark:text-yellow-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-500/20 dark:text-orange-300",
  urgent: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300",
};

export const STATUS_BADGE: Record<TaskStatus, string> = {
  todo: "bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-300",
  in_progress:
    "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300",
  done: "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300",
};

// Small accent strip shown on the left edge of a card, by priority.
export const PRIORITY_ACCENT: Record<TaskPriority, string> = {
  low: "bg-green-400 dark:bg-green-500/70",
  medium: "bg-yellow-400 dark:bg-yellow-500/70",
  high: "bg-orange-400 dark:bg-orange-500/70",
  urgent: "bg-red-500 dark:bg-red-500/80",
};

/** Format an ISO date for display, e.g. "Jun 20, 2026". Returns null if unset. */
export function formatDueDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Format an ISO timestamp with date + time, e.g. "Jun 20, 2026, 3:00 PM". */
export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** True when an open task's due date is in the past. */
export function isOverdue(
  dueDate: string | null | undefined,
  status: TaskStatus,
): boolean {
  if (!dueDate || status === "done") return false;
  const date = new Date(dueDate);
  return !Number.isNaN(date.getTime()) && date.getTime() < Date.now();
}

// "2026-06-20T15:00:00+00:00" -> "2026-06-20" for the native date input.
export function toDateInputValue(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "";
}
