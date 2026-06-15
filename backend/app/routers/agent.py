"""AI agent endpoints, mounted under ``/api/v1/agent``.

``/chat`` returns a single structured reply; ``/stream`` streams the same turn
as Server-Sent Events (token / thinking / tool_start / tool_end / done / error).
Both require authentication and operate only on the current user's tasks.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUser
from app.schemas.agent import ChatRequest, ChatResponse
from app.services import agent_service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse, summary="Chat with Taskify AI")
async def chat(payload: ChatRequest, current_user: CurrentUser) -> ChatResponse:
    """Send a message to the LangGraph agent and get a structured reply.

    The agent may call tools (search/create/update/prioritize/summarize) before
    answering; every tool call made during the turn is reported in ``tool_calls``.
    Pass ``session_id`` (returned here) on later turns to keep conversation memory.
    """

    try:
        result = await agent_service.chat(
            payload.message,
            payload.history,
            session_id=payload.session_id,
            user_id=current_user.id,
        )
    except Exception as exc:  # noqa: BLE001 - surface any agent/LLM failure cleanly
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent error: {exc}",
        ) from exc
    return ChatResponse(**result)


def _sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a single Server-Sent Event frame."""

    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream", summary="Stream a chat turn (SSE)")
async def stream(payload: ChatRequest, current_user: CurrentUser) -> StreamingResponse:
    """Stream the agent's turn as Server-Sent Events.

    Emits ``session``, ``thinking``, ``token``, ``tool_start``, ``tool_end`` and
    finally ``done`` (or ``error``). ``<think>`` reasoning is delivered only via
    ``thinking`` events and never appears in ``token`` events or the final answer.
    """

    async def event_source() -> AsyncIterator[str]:
        try:
            async for event_type, data in agent_service.stream(
                payload.message,
                payload.history,
                session_id=payload.session_id,
                user_id=current_user.id,
            ):
                yield _sse(event_type, data)
        except Exception as exc:  # noqa: BLE001 - last-resort guard for the stream
            yield _sse("error", {"message": f"Agent error: {exc}"})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
