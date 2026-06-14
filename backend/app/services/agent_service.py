"""Orchestration layer that drives the LangGraph agent for the chat endpoint."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.graph import get_graph
from app.agent.prompts import SYSTEM_PROMPT
from app.schemas.agent import ChatMessage


def _to_lc_messages(history: Iterable[ChatMessage | dict[str, Any]]) -> list[BaseMessage]:
    """Convert client-supplied history into LangChain message objects."""

    messages: list[BaseMessage] = []
    for item in history:
        if isinstance(item, ChatMessage):
            role, content = item.role, item.content
        else:
            role, content = item.get("role"), item.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
    return messages


def _extract_tool_calls(messages: Iterable[BaseMessage]) -> list[dict[str, Any]]:
    """Collect every tool call the agent made across the run."""

    calls: list[dict[str, Any]] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            calls.append(
                {
                    "name": call.get("name"),
                    "args": call.get("args", {}),
                    "id": call.get("id"),
                }
            )
    return calls


def _extract_tokens(messages: Iterable[BaseMessage]) -> int:
    """Sum token usage reported by the model across all AI messages."""

    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None)
        if usage:
            total += usage.get("total_tokens", 0) or 0
            continue
        metadata = getattr(message, "response_metadata", None) or {}
        total += (metadata.get("prompt_eval_count", 0) or 0) + (metadata.get("eval_count", 0) or 0)
    return total


def _stringify(content: Any) -> str:
    """Normalize message content (which may be a list of blocks) to text."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


async def chat(
    message: str, history: Iterable[ChatMessage | dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Run one turn through the agent graph and return a structured result.

    Returns a dict with ``response`` (str), ``tool_calls`` (list) and
    ``tokens_used`` (int).
    """

    graph = get_graph()
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_to_lc_messages(history or []))
    messages.append(HumanMessage(content=message))

    result = await graph.ainvoke({"messages": messages})
    output_messages = result["messages"]
    final_message = output_messages[-1]

    return {
        "response": _stringify(final_message.content).strip(),
        "tool_calls": _extract_tool_calls(output_messages),
        "tokens_used": _extract_tokens(output_messages),
    }
