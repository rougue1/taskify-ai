"use client";

import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";

import { cn } from "@/lib/utils";
import { STATUS_LABELS, type Task, type TaskStatus } from "@/types";

import { KanbanCard, type KanbanCardHandlers } from "./KanbanCard";

interface KanbanColumnProps {
  status: TaskStatus;
  tasks: Task[];
  handlers: KanbanCardHandlers;
}

export function KanbanColumn({ status, tasks, handlers }: KanbanColumnProps) {
  // The column id is the status string itself, so the board can drop onto an
  // empty column (where there is no card to drop "over").
  const { setNodeRef, isOver } = useDroppable({ id: status });
  const ids = tasks.map((task) => String(task.id));

  return (
    <div className="bg-muted/30 flex min-w-0 flex-col rounded-xl border md:h-full md:min-h-0">
      <div className="flex items-center justify-between gap-2 px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              status === "todo" && "bg-gray-400",
              status === "in_progress" && "bg-blue-500",
              status === "done" && "bg-green-500",
            )}
            aria-hidden
          />
          <h3 className="text-sm font-semibold">{STATUS_LABELS[status]}</h3>
          <span className="bg-muted text-muted-foreground inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-medium">
            {tasks.length}
          </span>
        </div>
      </div>

      <div
        ref={setNodeRef}
        className={cn(
          "space-y-2 rounded-b-xl px-2 pb-2 transition-colors md:min-h-0 md:flex-1 md:overflow-y-auto",
          isOver && "bg-primary/5",
        )}
      >
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          {tasks.map((task) => (
            <KanbanCard key={task.id} task={task} handlers={handlers} />
          ))}
        </SortableContext>

        {tasks.length === 0 && (
          <div className="text-muted-foreground/60 flex h-24 items-center justify-center rounded-lg border border-dashed text-xs">
            Drop tasks here
          </div>
        )}
      </div>
    </div>
  );
}
