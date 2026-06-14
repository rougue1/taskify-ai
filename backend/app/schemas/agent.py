"""Pydantic schemas for the AI agent chat endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single turn of conversation history sent by the client."""

    role: Literal["user", "assistant"]
    content: str
    tool_calls: list[dict[str, Any]] | None = None


class ChatRequest(BaseModel):
    """Request body for ``POST /api/v1/agent/chat``."""

    message: str = Field(..., min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


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
