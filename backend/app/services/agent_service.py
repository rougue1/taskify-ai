"""Orchestration layer that drives the LangGraph agent.

Provides both the blocking ``chat`` turn and the ``stream`` async generator that
backs the SSE endpoint. Conversation memory is real: server-side history per
``session_id`` is the authoritative context (it includes tool-call and
tool-result messages), and a client may alternatively replay ``history`` which
is faithfully reconstructed into LangChain message objects.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.errors import GraphRecursionError

from app.agent import sessions
from app.agent.context import user_context
from app.agent.graph import get_graph
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.thinking import ThinkStreamParser, strip_think
from app.config import settings
from app.schemas.agent import ChatMessage

_RECURSION_FALLBACK = (
    "I couldn't finish that — it needed too many steps. "
    "Could you simplify or rephrase the request?"
)
_EMPTY_ANSWER_FALLBACK = "Done."


def _unpack(item: ChatMessage | dict[str, Any]) -> tuple[str, str, list, str | None]:
    """Normalize a history item into (role, content, tool_calls, tool_call_id)."""

    if isinstance(item, ChatMessage):
        return item.role, item.content or "", item.tool_calls or [], item.tool_call_id
    return (
        item.get("role", ""),
        item.get("content", "") or "",
        item.get("tool_calls") or [],
        item.get("tool_call_id"),
    )


def _to_lc_messages(history: Iterable[ChatMessage | dict[str, Any]]) -> list[BaseMessage]:
    """Reconstruct client history into LangChain messages.

    Produces ``HumanMessage``/``AIMessage``/``ToolMessage`` objects. Tool-call
    plumbing is only kept when an assistant turn's tool calls are fully matched
    by following tool results, so the model is never handed an orphaned tool
    call (or an orphaned result), which Ollama would reject.
    """

    items = list(history)
    result_ids = {
        tc_id
        for role, _, _, tc_id in (_unpack(it) for it in items)
        if role == "tool" and tc_id
    }

    messages: list[BaseMessage] = []
    kept_call_ids: set[str] = set()
    for item in items:
        role, content, tool_calls, tool_call_id = _unpack(item)
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            valid_calls = [
                {
                    "name": tc.get("name"),
                    "args": tc.get("args", {}),
                    "id": tc.get("id"),
                    "type": "tool_call",
                }
                for tc in tool_calls
                if tc.get("id") and tc["id"] in result_ids
            ]
            if valid_calls:
                kept_call_ids.update(tc["id"] for tc in valid_calls)
                messages.append(
                    AIMessage(content=strip_think(content), tool_calls=valid_calls)
                )
            else:
                messages.append(AIMessage(content=strip_think(content)))
        elif role == "tool" and tool_call_id in kept_call_ids:
            messages.append(ToolMessage(content=content, tool_call_id=tool_call_id))
    return messages


def _resolve_session(
    session_id: str | None, history: Iterable[ChatMessage | dict[str, Any]] | None
) -> tuple[str, list[BaseMessage]]:
    """Pick the session id and its starting message list.

    Known session id -> authoritative server-side history. Unknown/absent ->
    a fresh (or client-seeded) conversation, keeping the client's id if given.
    """

    if session_id:
        stored = sessions.get(session_id)
        if stored is not None:
            return session_id, stored
        return session_id, _to_lc_messages(history or [])
    return sessions.new_session_id(), _to_lc_messages(history or [])


def _extract_tool_calls(messages: Iterable[BaseMessage]) -> list[dict[str, Any]]:
    """Collect every tool call the agent made across the run."""

    calls: list[dict[str, Any]] = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            calls.append(
                {"name": call.get("name"), "args": call.get("args", {}), "id": call.get("id")}
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


def _sanitize_ai_contents(messages: list[BaseMessage]) -> None:
    """Strip ``<think>`` reasoning from AI message contents in place.

    Ensures reasoning is never stored in history nor returned to the client.
    """

    for message in messages:
        if isinstance(message, AIMessage):
            message.content = strip_think(_stringify(message.content))


def _final_answer(messages: list[BaseMessage]) -> str:
    """Return the cleaned text of the final assistant message."""

    for message in reversed(messages):
        if isinstance(message, AIMessage):
            text = _stringify(message.content).strip()
            return text or _EMPTY_ANSWER_FALLBACK
    return _EMPTY_ANSWER_FALLBACK


async def chat(
    message: str,
    history: Iterable[ChatMessage | dict[str, Any]] | None = None,
    *,
    session_id: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Run one turn through the agent graph and return a structured result."""

    graph = get_graph()
    session_id, base = _resolve_session(session_id, history)
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT), *base]
    messages.append(HumanMessage(content=message))
    input_len = len(messages)
    config = {"recursion_limit": settings.AGENT_RECURSION_LIMIT}

    with user_context(user_id):
        try:
            result = await graph.ainvoke({"messages": messages}, config=config)
        except GraphRecursionError:
            convo = [*base, HumanMessage(content=message), AIMessage(content=_RECURSION_FALLBACK)]
            sessions.save(session_id, convo)
            return {
                "response": _RECURSION_FALLBACK,
                "tool_calls": [],
                "tokens_used": 0,
                "session_id": session_id,
            }

    output_messages: list[BaseMessage] = result["messages"]
    _sanitize_ai_contents(output_messages)
    sessions.save(session_id, output_messages)

    # Only this turn's new messages count toward the reported tool calls/tokens,
    # never the replayed conversation history.
    turn_messages = output_messages[input_len:] or output_messages
    return {
        "response": _final_answer(turn_messages),
        "tool_calls": _extract_tool_calls(turn_messages),
        "tokens_used": _extract_tokens(turn_messages),
        "session_id": session_id,
    }


def _truncate(value: Any, limit: int = 600) -> str:
    """Stringify and truncate a tool result for the SSE ``tool_end`` event."""

    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= limit else text[:limit] + "…"


async def stream(
    message: str,
    history: Iterable[ChatMessage | dict[str, Any]] | None = None,
    *,
    session_id: str | None = None,
    user_id: int | None = None,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """Stream a turn as ``(event_type, data)`` tuples.

    Event types: ``session``, ``thinking``, ``token``, ``tool_start``,
    ``tool_end``, ``done``, ``error``. ``<think>`` content is emitted only as
    ``thinking`` events and is never part of ``token`` events, the ``done``
    answer, or the stored history.
    """

    graph = get_graph()
    session_id, base = _resolve_session(session_id, history)
    messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT), *base]
    messages.append(HumanMessage(content=message))
    input_len = len(messages)
    config = {"recursion_limit": settings.AGENT_RECURSION_LIMIT}

    parser = ThinkStreamParser()
    answer_parts: list[str] = []
    tool_calls_seen: list[dict[str, Any]] = []
    final_state: dict[str, Any] | None = None

    yield "session", {"session_id": session_id}

    with user_context(user_id):
        try:
            async for event in graph.astream_events({"messages": messages}, config=config):
                kind = event.get("event")

                if kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    reasoning = getattr(chunk, "additional_kwargs", {}).get("reasoning_content")
                    if reasoning:
                        parser.saw_think = True
                        yield "thinking", {"content": reasoning}
                    for seg_kind, seg_text in parser.feed(_stringify(getattr(chunk, "content", ""))):
                        if seg_kind == "thinking":
                            yield "thinking", {"content": seg_text}
                        else:
                            answer_parts.append(seg_text)
                            yield "token", {"content": seg_text}

                elif kind == "on_tool_start":
                    call = {
                        "name": event.get("name"),
                        "args": (event.get("data") or {}).get("input", {}),
                        "id": event.get("run_id"),
                    }
                    tool_calls_seen.append(call)
                    yield "tool_start", call

                elif kind == "on_tool_end":
                    output = (event.get("data") or {}).get("output")
                    # ToolNode wraps results in a ToolMessage; show just its text.
                    if hasattr(output, "content"):
                        output = output.content
                    yield "tool_end", {
                        "name": event.get("name"),
                        "id": event.get("run_id"),
                        "output": _truncate(output),
                    }

                elif kind == "on_chain_end" and not event.get("parent_ids"):
                    output = (event.get("data") or {}).get("output")
                    if isinstance(output, dict) and "messages" in output:
                        final_state = output

            for seg_kind, seg_text in parser.flush():
                if seg_kind == "thinking":
                    yield "thinking", {"content": seg_text}
                else:
                    answer_parts.append(seg_text)
                    yield "token", {"content": seg_text}

        except GraphRecursionError:
            convo = [*base, HumanMessage(content=message), AIMessage(content=_RECURSION_FALLBACK)]
            sessions.save(session_id, convo)
            yield "error", {"message": _RECURSION_FALLBACK, "code": "recursion_limit"}
            return
        except Exception as exc:  # noqa: BLE001 - report any agent/LLM failure to the client
            yield "error", {"message": f"Agent error: {exc}"}
            return

    streamed_answer = "".join(answer_parts).strip()
    if final_state is not None:
        output_messages: list[BaseMessage] = final_state["messages"]
        _sanitize_ai_contents(output_messages)
        sessions.save(session_id, output_messages)
        turn_messages = output_messages[input_len:] or output_messages
        # Prefer the exact text the client streamed; fall back to final state.
        final_text = streamed_answer or _final_answer(turn_messages)
        tool_calls = _extract_tool_calls(turn_messages)
        tokens = _extract_tokens(turn_messages)
    else:
        final_text = streamed_answer or _EMPTY_ANSWER_FALLBACK
        convo = [*base, HumanMessage(content=message), AIMessage(content=final_text)]
        sessions.save(session_id, convo)
        tool_calls = tool_calls_seen
        tokens = 0

    yield "done", {
        "response": final_text,
        "tool_calls": tool_calls,
        "tokens_used": tokens,
        "session_id": session_id,
    }
