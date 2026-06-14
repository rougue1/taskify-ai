"use client";

import { ClipboardList, Plus } from "lucide-react";

import { TaskCard } from "@/components/TaskCard";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { useTaskStore } from "@/store/taskStore";
import type { Task } from "@/types";

interface TaskListProps {
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
  onCreate: () => void;
}

function SkeletonCard() {
  return (
    <Card className="gap-3">
      <CardHeader>
        <div className="bg-muted h-5 w-2/3 animate-pulse rounded" />
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="bg-muted h-3 w-full animate-pulse rounded" />
        <div className="bg-muted h-3 w-4/5 animate-pulse rounded" />
      </CardContent>
      <CardFooter className="justify-end">
        <div className="bg-muted h-7 w-24 animate-pulse rounded" />
      </CardFooter>
    </Card>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
      <ClipboardList className="text-muted-foreground mb-3 h-10 w-10" />
      <h3 className="text-lg font-medium">No tasks yet</h3>
      <p className="text-muted-foreground mt-1 mb-4 max-w-sm text-sm">
        Create your first task, or ask the Taskify AI assistant to add one for
        you.
      </p>
      <Button onClick={onCreate}>
        <Plus className="h-4 w-4" />
        New Task
      </Button>
    </div>
  );
}

export function TaskList({ onEdit, onDelete, onCreate }: TaskListProps) {
  const tasks = useTaskStore((state) => state.tasks);
  const isLoading = useTaskStore((state) => state.isLoading);
  const error = useTaskStore((state) => state.error);

  if (isLoading && tasks.length === 0) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <SkeletonCard key={index} />
        ))}
      </div>
    );
  }

  if (error && tasks.length === 0) {
    return (
      <div className="border-destructive/50 bg-destructive/5 text-destructive rounded-lg border p-4 text-sm">
        Failed to load tasks: {error}
      </div>
    );
  }

  if (tasks.length === 0) {
    return <EmptyState onCreate={onCreate} />;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {tasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
