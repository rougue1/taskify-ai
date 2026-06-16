"use client";

import { useEffect, useMemo, useState } from "react";
import { MessageSquare, Plus } from "lucide-react";

import { AuthGate } from "@/components/AuthGate";
import { ChatPanel } from "@/components/ChatPanel";
import { Header } from "@/components/Header";
import { KanbanBoard } from "@/components/kanban/KanbanBoard";
import type { KanbanCardHandlers } from "@/components/kanban/KanbanCard";
import { TaskDetailPanel } from "@/components/TaskDetailPanel";
import { TaskForm } from "@/components/TaskForm";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useTaskStore } from "@/store/taskStore";
import { type CreateTaskInput, type Task } from "@/types";

function Dashboard() {
  const fetchTasks = useTaskStore((state) => state.fetchTasks);
  const tasks = useTaskStore((state) => state.tasks);
  const total = useTaskStore((state) => state.total);
  const createTask = useTaskStore((state) => state.createTask);
  const updateTask = useTaskStore((state) => state.updateTask);
  const deleteTask = useTaskStore((state) => state.deleteTask);
  const moveTaskStatus = useTaskStore((state) => state.moveTaskStatus);

  const [chatOpen, setChatOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  // Look the selected task up live so inline edits / drags keep the panel fresh.
  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedId) ?? null,
    [tasks, selectedId],
  );

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };

  const handlers: KanbanCardHandlers = {
    onSelect: (task) => setSelectedId(task.id),
    onEdit: (task) => {
      setEditing(task);
      setDialogOpen(true);
    },
    onDelete: (task) => {
      void deleteTask(task.id);
    },
    onToggleComplete: (task) => {
      void moveTaskStatus(task.id, task.status === "done" ? "todo" : "done");
    },
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
      // error surfaced via toast; keep the dialog open so the user can retry
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
            <div>
              <h1 className="text-base font-semibold">Board</h1>
              <p className="text-muted-foreground text-xs">
                {total} task{total === 1 ? "" : "s"} · drag cards between columns
              </p>
            </div>
            <Button size="sm" onClick={openCreate} className="shrink-0">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">New Task</span>
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 sm:p-6 md:overflow-hidden">
            <KanbanBoard handlers={handlers} />
          </div>
        </main>

        <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
      </div>

      {!chatOpen && (
        <Button
          onClick={() => setChatOpen(true)}
          size="icon"
          className="fixed right-6 bottom-6 z-30 h-12 w-12 rounded-full shadow-lg"
          aria-label="Open chat"
        >
          <MessageSquare className="h-5 w-5" />
        </Button>
      )}

      <TaskDetailPanel
        task={selectedTask}
        onClose={() => setSelectedId(null)}
        onEdit={(task) => {
          setEditing(task);
          setDialogOpen(true);
        }}
        onDelete={(task) => {
          void deleteTask(task.id);
        }}
      />

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
