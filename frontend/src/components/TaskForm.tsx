"use client";

import { useState } from "react";
import { X } from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  TASK_PRIORITIES,
  TASK_STATUSES,
  type CreateTaskInput,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "@/types";

interface TaskFormProps {
  task?: Task;
  submitting?: boolean;
  onSubmit: (input: CreateTaskInput) => void;
  onCancel: () => void;
}

// "2026-06-20T15:00:00+00:00" -> "2026-06-20" for the native date input.
function toDateInput(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "";
}

export function TaskForm({
  task,
  submitting,
  onSubmit,
  onCancel,
}: TaskFormProps) {
  const [title, setTitle] = useState(task?.title ?? "");
  const [description, setDescription] = useState(task?.description ?? "");
  const [status, setStatus] = useState<TaskStatus>(task?.status ?? "todo");
  const [priority, setPriority] = useState<TaskPriority>(
    task?.priority ?? "medium",
  );
  const [tags, setTags] = useState<string[]>(task?.tags ?? []);
  const [tagInput, setTagInput] = useState("");
  const [dueDate, setDueDate] = useState(toDateInput(task?.due_date));
  const [error, setError] = useState<string | null>(null);

  const addTag = (raw: string) => {
    const value = raw.trim().replace(/,$/, "").trim();
    if (!value) return;
    setTags((current) =>
      current.includes(value) ? current : [...current, value],
    );
    setTagInput("");
  };

  const removeTag = (value: string) => {
    setTags((current) => current.filter((tag) => tag !== value));
  };

  const handleTagKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addTag(tagInput);
    } else if (event.key === "Backspace" && !tagInput && tags.length > 0) {
      removeTag(tags[tags.length - 1]);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    // Fold a half-typed tag into the list on submit.
    const finalTags = tagInput.trim() ? [...tags, tagInput.trim()] : tags;
    onSubmit({
      title: title.trim(),
      description: description.trim() || null,
      status,
      priority,
      tags: finalTags,
      due_date: dueDate ? dueDate : null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="e.g. Ship the v0.1 scaffold"
          autoFocus
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Optional details..."
          rows={3}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label>Status</Label>
          <Select
            value={status}
            onValueChange={(value) => setStatus(value as TaskStatus)}
          >
            <SelectTrigger className="w-full">
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
        </div>

        <div className="space-y-2">
          <Label>Priority</Label>
          <Select
            value={priority}
            onValueChange={(value) => setPriority(value as TaskPriority)}
          >
            <SelectTrigger className="w-full">
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
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="due-date">Due date</Label>
        <Input
          id="due-date"
          type="date"
          value={dueDate}
          onChange={(event) => setDueDate(event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="tags">Tags</Label>
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((tag) => (
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
          id="tags"
          value={tagInput}
          onChange={(event) => setTagInput(event.target.value)}
          onKeyDown={handleTagKeyDown}
          onBlur={() => addTag(tagInput)}
          placeholder="Type a tag and press Enter"
        />
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting}>
          {submitting ? "Saving..." : task ? "Save changes" : "Create task"}
        </Button>
      </div>
    </form>
  );
}
