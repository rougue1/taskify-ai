"""Pydantic schemas for the AI agent chat endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single turn of conversation history sent by the client.

    ``role`` may be ``tool`` for a tool result (carrying ``tool_call_id``); an
    ``assistant`` turn may carry ``tool_calls`` it made. These let the server
    reconstruct faithful LangChain messages when a client replays history.
    """

    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    """Request body for the agent chat/stream endpoints."""

    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)
    # When present and known to the server, server-side history is authoritative
    # and ``history`` above is ignored. Omit on the first turn to start a session.
    session_id: str | None = None


class ToolCall(BaseModel):
    """A tool invocation made by the agent during a turn."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    id: str | None = None


class ChatResponse(BaseModel):
    """Response body for ``POST /api/v1/agent/chat``."""

    response: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tokens_used: int = 0
    session_id: str
