"""CRUD endpoints for tasks, mounted under ``/api/v1/tasks``.

All routes require authentication and operate only on the current user's tasks.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import CurrentUser
from app.models.task import TaskPriority, TaskStatus
from app.schemas.task import (
    BulkUpdateRequest,
    BulkUpdateResponse,
    PaginatedTasks,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SortOrder,
    TaskCreate,
    TaskRead,
    TaskSortField,
    TaskUpdate,
)
from app.services import embedding, task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=PaginatedTasks, summary="List tasks")
async def list_tasks(
    current_user: CurrentUser,
    session: SessionDep,
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = Query(default=None),
    sort_by: TaskSortField = Query(default=TaskSortField.created_at),
    sort_order: SortOrder = Query(default=SortOrder.desc),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedTasks:
    """List the current user's tasks with filtering, sorting and pagination."""

    items, total = await task_service.list_tasks_page(
        session,
        user_id=current_user.id,
        status=status_filter,
        priority=priority,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size if page_size else 0
    return PaginatedTasks(
        items=[TaskRead.model_validate(task) for task in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
async def create_task(
    payload: TaskCreate, current_user: CurrentUser, session: SessionDep
) -> TaskRead:
    """Create a new task owned by the current user."""

    return await task_service.create_task(session, payload, user_id=current_user.id)


@router.patch("/bulk", response_model=BulkUpdateResponse, summary="Bulk update tasks")
async def bulk_update_tasks(
    payload: BulkUpdateRequest, current_user: CurrentUser, session: SessionDep
) -> BulkUpdateResponse:
    """Apply one partial update to many of the current user's tasks at once.

    Declared before ``/{task_id}`` so the literal ``/bulk`` path is not parsed as
    a task id. Only tasks owned by the user are affected; unknown ids are ignored.
    """

    tasks = await task_service.bulk_update(
        session, payload.ids, payload.update, user_id=current_user.id
    )
    return BulkUpdateResponse(
        updated=[TaskRead.model_validate(task) for task in tasks], count=len(tasks)
    )


@router.post(
    "/semantic-search",
    response_model=SemanticSearchResponse,
    summary="Semantic search over tasks",
)
async def semantic_search_tasks(
    payload: SemanticSearchRequest, current_user: CurrentUser, session: SessionDep
) -> SemanticSearchResponse:
    """Return the user's most semantically similar tasks for a query.

    When the RAG stack (PostgreSQL + pgvector + embedding model) is unavailable,
    responds with ``available: false`` and an empty list rather than erroring.
    """

    results = await embedding.semantic_search(
        session, user_id=current_user.id, query=payload.query, limit=5
    )
    if results is None:
        return SemanticSearchResponse(query=payload.query, available=False, items=[])
    return SemanticSearchResponse(
        query=payload.query,
        available=True,
        items=[TaskRead.model_validate(task) for task in results],
    )


@router.get("/{task_id}", response_model=TaskRead, summary="Get a task")
async def get_task(task_id: int, current_user: CurrentUser, session: SessionDep) -> TaskRead:
    """Fetch a single task by id."""

    task = await task_service.get_task(session, task_id, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead, summary="Update a task")
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> TaskRead:
    """Partially update a task; only provided fields are changed."""

    task = await task_service.update_task(session, task_id, payload, user_id=current_user.id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
async def delete_task(
    task_id: int, current_user: CurrentUser, session: SessionDep
) -> None:
    """Delete a task and return ``204 No Content``."""

    deleted = await task_service.delete_task(session, task_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
