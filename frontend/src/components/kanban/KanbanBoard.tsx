"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  closestCorners,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";

import { useTaskStore } from "@/store/taskStore";
import { type Task, type TaskStatus } from "@/types";

import { KanbanCardBody, type KanbanCardHandlers } from "./KanbanCard";
import { KanbanColumn } from "./KanbanColumn";

const COLUMN_ORDER: TaskStatus[] = ["todo", "in_progress", "done"];

type Columns = Record<TaskStatus, string[]>;

function groupIds(tasks: Task[]): Columns {
  const columns: Columns = { todo: [], in_progress: [], done: [] };
  for (const task of tasks) columns[task.status]?.push(String(task.id));
  return columns;
}

interface KanbanBoardProps {
  handlers: KanbanCardHandlers;
}

export function KanbanBoard({ handlers }: KanbanBoardProps) {
  const tasks = useTaskStore((state) => state.tasks);
  const isLoading = useTaskStore((state) => state.isLoading);
  const error = useTaskStore((state) => state.error);
  const setTasks = useTaskStore((state) => state.setTasks);
  const moveTaskStatus = useTaskStore((state) => state.moveTaskStatus);

  const tasksById = useMemo(() => {
    const map = new Map<string, Task>();
    for (const task of tasks) map.set(String(task.id), task);
    return map;
  }, [tasks]);

  const [columns, setColumns] = useState<Columns>(() => groupIds(tasks));
  const [activeId, setActiveId] = useState<string | null>(null);
  // True only between drag start and end, so we don't clobber the in-flight
  // local ordering when the store's task array updates mid-drag.
  const draggingRef = useRef(false);

  // Keep the board in sync with the store whenever it changes and we're idle.
  useEffect(() => {
    if (!draggingRef.current) setColumns(groupIds(tasks));
  }, [tasks]);

  const sensors = useSensors(
    // A small activation distance lets a plain click open the detail panel
    // without the press being interpreted as a drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const findColumn = (id: string): TaskStatus | undefined => {
    if (id in columns) return id as TaskStatus;
    return COLUMN_ORDER.find((status) => columns[status].includes(id));
  };

  const handleDragStart = (event: DragStartEvent) => {
    draggingRef.current = true;
    setActiveId(String(event.active.id));
  };

  // Live cross-column move: relocate the dragged id into the column it currently
  // hovers, which renders the placeholder gap where it would land.
  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over) return;
    const activeKey = String(active.id);
    const overKey = String(over.id);
    const from = findColumn(activeKey);
    const to = findColumn(overKey);
    if (!from || !to || from === to) return;

    setColumns((prev) => {
      const fromItems = prev[from];
      const toItems = prev[to];
      if (!fromItems.includes(activeKey)) return prev;
      const overIsColumn = overKey in prev;
      const insertAt = overIsColumn
        ? toItems.length
        : Math.max(0, toItems.indexOf(overKey));
      return {
        ...prev,
        [from]: fromItems.filter((id) => id !== activeKey),
        [to]: [...toItems.slice(0, insertAt), activeKey, ...toItems.slice(insertAt)],
      };
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    draggingRef.current = false;
    setActiveId(null);

    const activeKey = String(active.id);
    if (!over) {
      setColumns(groupIds(tasks));
      return;
    }

    const overKey = String(over.id);
    const destination = findColumn(activeKey);
    if (!destination) {
      setColumns(groupIds(tasks));
      return;
    }

    // Reorder within the destination column if dropped over a sibling card.
    let next = columns;
    if (!(overKey in columns)) {
      const items = columns[destination];
      const oldIndex = items.indexOf(activeKey);
      const newIndex = items.indexOf(overKey);
      if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
        next = { ...columns, [destination]: arrayMove(items, oldIndex, newIndex) };
        setColumns(next);
      }
    }

    // Commit the new order + column membership to the store (visual, no network),
    // then persist only the status change with a single PATCH.
    const ordered: Task[] = [];
    for (const status of COLUMN_ORDER) {
      for (const id of next[status]) {
        const task = tasksById.get(id);
        if (task) ordered.push(task.status === status ? task : { ...task, status });
      }
    }
    setTasks(ordered);

    const moved = tasksById.get(activeKey);
    if (moved && moved.status !== destination) {
      void moveTaskStatus(moved.id, destination);
    }
  };

  const handleDragCancel = () => {
    draggingRef.current = false;
    setActiveId(null);
    setColumns(groupIds(tasks));
  };

  if (isLoading && tasks.length === 0) {
    return (
      <div className="grid grid-cols-1 gap-4 md:h-full md:grid-cols-3">
        {COLUMN_ORDER.map((status) => (
          <div key={status} className="bg-muted/30 rounded-xl border p-3">
            <div className="bg-muted mb-3 h-5 w-24 animate-pulse rounded" />
            <div className="space-y-2">
              {[0, 1, 2].map((index) => (
                <div key={index} className="bg-muted h-20 animate-pulse rounded-lg" />
              ))}
            </div>
          </div>
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

  const activeTask = activeId ? tasksById.get(activeId) : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={handleDragCancel}
    >
      <div className="grid grid-cols-1 gap-4 md:h-full md:grid-cols-3">
        {COLUMN_ORDER.map((status) => (
          <KanbanColumn
            key={status}
            status={status}
            tasks={columns[status]
              .map((id) => tasksById.get(id))
              .filter((task): task is Task => Boolean(task))}
            handlers={handlers}
          />
        ))}
      </div>

      <DragOverlay>
        {activeTask ? (
          <div className="w-72 max-w-full">
            <KanbanCardBody task={activeTask} handlers={handlers} dragging />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
