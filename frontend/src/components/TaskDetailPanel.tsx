"use client";

import { useEffect, useState } from "react";
import { Pencil, Trash2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import {
  formatDateTime,
  PRIORITY_BADGE,
  STATUS_BADGE,
  toDateInputValue,
} from "@/lib/taskStyles";
import { useTaskStore } from "@/store/taskStore";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "@/types";

interface TaskDetailPanelProps {
  task: Task | null;
  onClose: () => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-muted-foreground text-xs tracking-wide uppercase">
        {label}
      </Label>
      {children}
    </div>
  );
}

export function TaskDetailPanel({
  task,
  onClose,
  onEdit,
  onDelete,
}: TaskDetailPanelProps) {
  const updateTask = useTaskStore((state) => state.updateTask);
  // Retain the last task while the panel slides out so its content doesn't
  // vanish mid-animation; refreshed live from the store whenever it's open.
  const [shown, setShown] = useState<Task | null>(task);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [tagInput, setTagInput] = useState("");

  const open = Boolean(task);

  useEffect(() => {
    if (task) setShown(task);
  }, [task]);

  // Reset transient UI state each time a (different) task is opened.
  useEffect(() => {
    setConfirmingDelete(false);
    setTagInput("");
  }, [task?.id]);

  // Escape closes the panel.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const patch = (changes: Parameters<typeof updateTask>[1]) => {
    if (!shown) return;
    void updateTask(shown.id, changes);
  };

  const addTag = (raw: string) => {
    const value = raw.trim().replace(/,$/, "").trim();
    if (!value || !shown) return;
    const current = shown.tags ?? [];
    if (!current.includes(value)) patch({ tags: [...current, value] });
    setTagInput("");
  };

  const removeTag = (value: string) => {
    if (!shown) return;
    patch({ tags: (shown.tags ?? []).filter((tag) => tag !== value) });
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        aria-hidden
        className={cn(
          "fixed inset-0 z-40 bg-black/40 transition-opacity duration-300",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />

      {/* Sliding panel */}
      <aside
        role="dialog"
        aria-label="Task details"
        aria-modal="true"
        className={cn(
          "bg-card fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l shadow-xl transition-transform duration-300 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        {shown && (
          <>
            <div className="flex items-center justify-between border-b px-5 py-3.5">
              <h2 className="text-sm font-semibold">Task details</h2>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                aria-label="Close panel"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
              <div className="space-y-2">
                <h3 className="text-lg leading-snug font-semibold break-words">
                  {shown.title}
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  <Badge className={cn("border-0", STATUS_BADGE[shown.status])}>
                    {STATUS_LABELS[shown.status]}
                  </Badge>
                  <Badge className={cn("border-0", PRIORITY_BADGE[shown.priority])}>
                    {PRIORITY_LABELS[shown.priority]}
                  </Badge>
                </div>
              </div>

              <Field label="Description">
                {shown.description ? (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {shown.description}
                  </p>
                ) : (
                  <p className="text-muted-foreground text-sm italic">
                    No description
                  </p>
                )}
              </Field>

              <div className="grid grid-cols-2 gap-4">
                <Field label="Status">
                  <Select
                    value={shown.status}
                    onValueChange={(value) => patch({ status: value as TaskStatus })}
                  >
                    <SelectTrigger size="sm" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TASK_STATUSES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {STATUS_LABELS[value]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>

                <Field label="Priority">
                  <Select
                    value={shown.priority}
                    onValueChange={(value) =>
                      patch({ priority: value as TaskPriority })
                    }
                  >
                    <SelectTrigger size="sm" className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TASK_PRIORITIES.map((value) => (
                        <SelectItem key={value} value={value}>
                          {PRIORITY_LABELS[value]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>

              <Field label="Due date">
                <Input
                  type="date"
                  value={toDateInputValue(shown.due_date)}
                  onChange={(event) =>
                    patch({ due_date: event.target.value || null })
                  }
                  className="w-full"
                />
              </Field>

              <Field label="Tags">
                {shown.tags && shown.tags.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {shown.tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="gap-1 pr-1">
                        {tag}
                        <button
                          type="button"
                          onClick={() => removeTag(tag)}
                          aria-label={`Remove ${tag}`}
                          className="hover:text-foreground/80 ml-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
                <Input
                  value={tagInput}
                  onChange={(event) => setTagInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === ",") {
                      event.preventDefault();
                      addTag(tagInput);
                    } else if (
                      event.key === "Backspace" &&
                      !tagInput &&
                      shown.tags &&
                      shown.tags.length > 0
                    ) {
                      removeTag(shown.tags[shown.tags.length - 1]);
                    }
                  }}
                  onBlur={() => addTag(tagInput)}
                  placeholder="Add a tag and press Enter"
                />
              </Field>

              <div className="text-muted-foreground grid grid-cols-2 gap-4 border-t pt-4 text-xs">
                <div>
                  <div className="font-medium">Created</div>
                  <div>{formatDateTime(shown.created_at) ?? "—"}</div>
                </div>
                <div>
                  <div className="font-medium">Updated</div>
                  <div>{formatDateTime(shown.updated_at) ?? "—"}</div>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 border-t px-5 py-3.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onEdit(shown)}
                className="flex-1"
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit
              </Button>
              {confirmingDelete ? (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => {
                    onDelete(shown);
                    onClose();
                  }}
                  className="flex-1"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Confirm delete
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setConfirmingDelete(true)}
                  className="flex-1"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </Button>
              )}
            </div>
          </>
        )}
      </aside>
    </>
  );
}
