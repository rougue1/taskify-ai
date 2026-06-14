"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus } from "lucide-react";

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
import { useTaskStore } from "@/store/taskStore";
import type { CreateTaskInput, Task, TaskStatus } from "@/types";

const FILTERS: { label: string; value: TaskStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "To Do", value: "todo" },
  { label: "In Progress", value: "in_progress" },
  { label: "Done", value: "done" },
];

export default function Home() {
  const fetchTasks = useTaskStore((state) => state.fetchTasks);
  const setFilters = useTaskStore((state) => state.setFilters);
  const createTask = useTaskStore((state) => state.createTask);
  const updateTask = useTaskStore((state) => state.updateTask);
  const deleteTask = useTaskStore((state) => state.deleteTask);

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
      // error is surfaced via the store; nothing else to do here
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
      <Header onToggleChat={() => setChatOpen((open) => !open)} />

      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
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
            <Button size="sm" onClick={openCreate} className="shrink-0">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">New Task</span>
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 sm:p-6">
            <TaskList
              onEdit={openEdit}
              onDelete={handleDelete}
              onCreate={openCreate}
            />
          </div>
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
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditing(null);
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
