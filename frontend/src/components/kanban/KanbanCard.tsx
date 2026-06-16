"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Calendar, Check, Pencil, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  formatDueDate,
  isOverdue,
  PRIORITY_ACCENT,
  PRIORITY_BADGE,
} from "@/lib/taskStyles";
import { PRIORITY_LABELS, type Task } from "@/types";

export interface KanbanCardHandlers {
  onSelect: (task: Task) => void;
  onEdit: (task: Task) => void;
  onDelete: (task: Task) => void;
  onToggleComplete: (task: Task) => void;
}

// A small icon button that never starts a drag (stops the pointer from reaching
// the card's drag listeners) and never bubbles its click up to card selection.
function CardActionButton({
  label,
  onClick,
  className,
  children,
}: {
  label: string;
  onClick: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className={cn(
        "flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-background hover:text-foreground",
        className,
      )}
    >
      {children}
    </button>
  );
}

// Presentational card body — shared by the live (sortable) card and the floating
// drag overlay so they look identical while dragging.
export function KanbanCardBody({
  task,
  handlers,
  dragging = false,
}: {
  task: Task;
  handlers: KanbanCardHandlers;
  dragging?: boolean;
}) {
  const due = formatDueDate(task.due_date);
  const overdue = isOverdue(task.due_date, task.status);
  const done = task.status === "done";

  return (
    <div
      onClick={() => handlers.onSelect(task)}
      className={cn(
        "group/card bg-card relative flex cursor-grab flex-col gap-2 overflow-hidden rounded-lg border p-3 pl-4 text-left shadow-sm transition-shadow hover:shadow-md active:cursor-grabbing",
        dragging && "rotate-2 cursor-grabbing shadow-lg ring-2 ring-primary/40",
      )}
    >
      {/* Priority accent strip. */}
      <span
        className={cn(
          "absolute inset-y-0 left-0 w-1.5",
          PRIORITY_ACCENT[task.priority],
        )}
        aria-hidden
      />

      <div className="flex items-start justify-between gap-2">
        <h4
          className={cn(
            "text-sm leading-snug font-semibold break-words",
            done && "text-muted-foreground line-through",
          )}
        >
          {task.title}
        </h4>

        {/* Hover actions: quick-complete, edit, delete. */}
        <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover/card:opacity-100 focus-within:opacity-100">
          <CardActionButton
            label={done ? "Mark as to-do" : "Mark done"}
            onClick={() => handlers.onToggleComplete(task)}
            className={cn(
              done
                ? "bg-green-500/15 text-green-600 dark:text-green-400"
                : "hover:text-green-600 dark:hover:text-green-400",
            )}
          >
            <Check className="h-3.5 w-3.5" />
          </CardActionButton>
          <CardActionButton label="Edit task" onClick={() => handlers.onEdit(task)}>
            <Pencil className="h-3.5 w-3.5" />
          </CardActionButton>
          <CardActionButton
            label="Delete task"
            onClick={() => handlers.onDelete(task)}
            className="hover:text-destructive"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </CardActionButton>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <Badge className={cn("border-0", PRIORITY_BADGE[task.priority])}>
          {PRIORITY_LABELS[task.priority]}
        </Badge>
        {due && (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-xs",
              overdue ? "text-destructive font-medium" : "text-muted-foreground",
            )}
            title={overdue ? "Overdue" : "Due date"}
          >
            <Calendar className="h-3 w-3" />
            {due}
          </span>
        )}
      </div>

      {task.tags && task.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {task.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="text-[0.65rem] font-normal">
              {tag}
            </Badge>
          ))}
        </div>
      )}

      {task.description && (
        <p className="text-muted-foreground line-clamp-1 text-xs">
          {task.description}
        </p>
      )}
    </div>
  );
}

// The live, sortable card placed inside a column.
export function KanbanCard({
  task,
  handlers,
}: {
  task: Task;
  handlers: KanbanCardHandlers;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: String(task.id) });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      // While dragging, the original collapses to a faint placeholder; the
      // DragOverlay renders the floating copy the cursor carries.
      className={cn("touch-none", isDragging && "opacity-40")}
    >
      <KanbanCardBody task={task} handlers={handlers} />
    </div>
  );
}
