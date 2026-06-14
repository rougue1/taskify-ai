"use client";

import { Pencil, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  PRIORITY_LABELS,
  STATUS_LABELS,
  type Task,
  type TaskPriority,
  type TaskStatus,
} from "@/types";

const STATUS_STYLES: Record<TaskStatus, string> = {
  todo: "bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-300",
  in_progress:
    "bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300",
  done: "bg-green-100 text-green-700 dark:bg-green-500/20 dark:text-green-300",
};

const PRIORITY_STYLES: Record<TaskPriority, string> = {
  low: "bg-gray-100 text-gray-700 dark:bg-gray-500/20 dark:text-gray-300",
  medium:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-500/20 dark:text-yellow-300",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-500/20 dark:text-orange-300",
  urgent: "bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300",
};

interface TaskCardProps {
  task: Task;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
}

export function TaskCard({ task, onEdit, onDelete }: TaskCardProps) {
  return (
    <Card className="gap-3 transition-shadow hover:shadow-md">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-base leading-snug break-words">
            {task.title}
          </CardTitle>
          <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
            <Badge className={cn("border-0", STATUS_STYLES[task.status])}>
              {STATUS_LABELS[task.status]}
            </Badge>
            <Badge className={cn("border-0", PRIORITY_STYLES[task.priority])}>
              {PRIORITY_LABELS[task.priority]}
            </Badge>
          </div>
        </div>
      </CardHeader>

      {task.description && (
        <CardContent>
          <p className="text-muted-foreground line-clamp-3 text-sm">
            {task.description}
          </p>
        </CardContent>
      )}

      <CardFooter className="justify-between">
        <div className="flex flex-wrap gap-1">
          {task.tags?.map((tag) => (
            <Badge key={tag} variant="outline" className="text-xs font-normal">
              {tag}
            </Badge>
          ))}
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(task)}
            aria-label="Edit task"
          >
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => onDelete(task)}
            aria-label="Delete task"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Delete
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
