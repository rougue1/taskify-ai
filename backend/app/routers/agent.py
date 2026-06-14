"""AI agent chat endpoint, mounted under ``/api/v1/agent``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.agent import ChatRequest, ChatResponse
from app.services import agent_service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse, summary="Chat with Taskify AI")
async def chat(payload: ChatRequest) -> ChatResponse:
    """Send a message to the LangGraph agent and get a structured reply.

    The agent may call tools (search/create/update/summarize) before answering;
    every tool call made during the turn is reported in ``tool_calls``.
    """

    # TODO v0.4: convert to SSE streaming
    try:
        result = await agent_service.chat(payload.message, payload.history)
    except Exception as exc:  # noqa: BLE001 - surface any agent/LLM failure cleanly
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent error: {exc}",
        ) from exc
    return ChatResponse(**result)
