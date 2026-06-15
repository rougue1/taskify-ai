"use client";

import { useEffect, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  ChevronLeft,
  ChevronRight,
  MessageSquare,
  Plus,
} from "lucide-react";

import { AuthGate } from "@/components/AuthGate";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { TaskForm } from "@/components/TaskForm";
import { TaskList } from "@/components/TaskList";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTaskStore } from "@/store/taskStore";
import {
  SORT_FIELD_LABELS,
  type CreateTaskInput,
  type Task,
  type TaskSortField,
  type TaskStatus,
} from "@/types";

const FILTERS: { label: string; value: TaskStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "To Do", value: "todo" },
  { label: "In Progress", value: "in_progress" },
  { label: "Done", value: "done" },
];

const SORT_FIELDS: TaskSortField[] = [
  "created_at",
  "updated_at",
  "due_date",
  "priority",
  "title",
];

function Dashboard() {
  const fetchTasks = useTaskStore((state) => state.fetchTasks);
  const setFilters = useTaskStore((state) => state.setFilters);
  const setSort = useTaskStore((state) => state.setSort);
  const setPage = useTaskStore((state) => state.setPage);
  const createTask = useTaskStore((state) => state.createTask);
  const updateTask = useTaskStore((state) => state.updateTask);
  const deleteTask = useTaskStore((state) => state.deleteTask);
  const sortBy = useTaskStore((state) => state.sortBy);
  const sortOrder = useTaskStore((state) => state.sortOrder);
  const page = useTaskStore((state) => state.page);
  const pages = useTaskStore((state) => state.pages);
  const total = useTaskStore((state) => state.total);

  const [activeFilter, setActiveFilter] = useState<TaskStatus | "all">("all");
  const [chatOpen, setChatOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  const handleFilter = (value: TaskStatus | "all") => {
    setActiveFilter(value);
    setFilters(value === "all" ? {} : { status: value });
  };

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const openEdit = (task: Task) => {
    setEditing(task);
    setDialogOpen(true);
  };

  const handleDelete = async (task: Task) => {
    try {
      await deleteTask(task.id);
    } catch {
      // error surfaced via toast; nothing else to do here
    }
  };

  const handleSubmit = async (input: CreateTaskInput) => {
    setSubmitting(true);
    try {
      if (editing) {
        await updateTask(editing.id, input);
      } else {
        await createTask(input);
      }
      setDialogOpen(false);
      setEditing(null);
    } catch {
      // keep the dialog open so the user can retry
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <Header onToggleChat={() => setChatOpen((value) => !value)} />

      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
            <div className="flex gap-1 overflow-x-auto">
              {FILTERS.map((filter) => (
                <Button
                  key={filter.value}
                  variant={activeFilter === filter.value ? "default" : "ghost"}
                  size="sm"
                  onClick={() => handleFilter(filter.value)}
                >
                  {filter.label}
                </Button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <Select
                value={sortBy}
                onValueChange={(value) => setSort(value as TaskSortField, sortOrder)}
              >
                <SelectTrigger size="sm" className="w-[8.5rem]">
                  <span className="text-muted-foreground mr-1 text-xs">Sort:</span>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SORT_FIELDS.map((field) => (
                    <SelectItem key={field} value={field}>
                      {SORT_FIELD_LABELS[field]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setSort(sortBy, sortOrder === "asc" ? "desc" : "asc")}
                aria-label={`Sort ${sortOrder === "asc" ? "descending" : "ascending"}`}
                title={sortOrder === "asc" ? "Ascending" : "Descending"}
              >
                {sortOrder === "asc" ? (
                  <ArrowUp className="h-4 w-4" />
                ) : (
                  <ArrowDown className="h-4 w-4" />
                )}
              </Button>
              <Button size="sm" onClick={openCreate} className="shrink-0">
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">New Task</span>
              </Button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4 sm:p-6">
            <TaskList onEdit={openEdit} onDelete={handleDelete} onCreate={openCreate} />
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-between border-t px-4 py-3 text-sm sm:px-6">
              <span className="text-muted-foreground">
                Page {page} of {pages} · {total} task{total === 1 ? "" : "s"}
              </span>
              <div className="flex gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page - 1)}
                  disabled={page <= 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Prev
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= pages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </main>

        <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
      </div>

      {!chatOpen && (
        <Button
          onClick={() => setChatOpen(true)}
          size="icon"
          className="fixed right-6 bottom-6 h-12 w-12 rounded-full shadow-lg"
          aria-label="Open chat"
        >
          <MessageSquare className="h-5 w-5" />
        </Button>
      )}

      <Dialog
        open={dialogOpen}
        onOpenChange={(value) => {
          setDialogOpen(value);
          if (!value) setEditing(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit task" : "New task"}</DialogTitle>
            <DialogDescription>
              {editing
                ? "Update the details of your task."
                : "Add a new task to your list."}
            </DialogDescription>
          </DialogHeader>
          <TaskForm
            task={editing ?? undefined}
            submitting={submitting}
            onSubmit={handleSubmit}
            onCancel={() => setDialogOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function Home() {
  return (
    <AuthGate>
      <Dashboard />
    </AuthGate>
  );
}
