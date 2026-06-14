"""CRUD endpoints for tasks, mounted under ``/api/v1/tasks``."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskRead], summary="List tasks")
async def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[TaskRead]:
    """List all tasks, optionally filtered by ``status`` and/or ``priority``."""

    return await task_service.list_tasks(session, status=status_filter, priority=priority)


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
async def create_task(
    payload: TaskCreate, session: AsyncSession = Depends(get_session)
) -> TaskRead:
    """Create a new task."""

    return await task_service.create_task(session, payload)


@router.get("/{task_id}", response_model=TaskRead, summary="Get a task")
async def get_task(task_id: int, session: AsyncSession = Depends(get_session)) -> TaskRead:
    """Fetch a single task by id."""

    task = await task_service.get_task(session, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead, summary="Update a task")
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    """Partially update a task; only provided fields are changed."""

    task = await task_service.update_task(session, task_id, payload)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """Delete a task and return ``204 No Content``."""

    deleted = await task_service.delete_task(session, task_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
