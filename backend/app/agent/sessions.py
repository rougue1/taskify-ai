"""In-memory, per-session conversation history for the agent.

Each ``session_id`` maps to the full LangChain message list for that
conversation — including ``AIMessage`` tool-call turns and ``ToolMessage``
results — so a follow-up turn has the complete context (real memory).

State lives in process memory only: it is intentionally ephemeral and resets on
restart. A future milestone can swap this module for a Redis/DB-backed store
without touching callers.
"""

from __future__ import annotations

import uuid

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

# Hard cap on stored messages per session to bound memory use. When exceeded,
# history is trimmed from the oldest end at a HumanMessage boundary so we never
# leave a dangling tool-call/tool-result pair at the front.
_MAX_MESSAGES = 60

_store: dict[str, list[BaseMessage]] = {}


def new_session_id() -> str:
    """Return a fresh, unique session id."""

    return uuid.uuid4().hex


def get(session_id: str) -> list[BaseMessage] | None:
    """Return a copy of the stored history for ``session_id``, or ``None``."""

    history = _store.get(session_id)
    return list(history) if history is not None else None


def _trim(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Bound history length, cutting only at a HumanMessage boundary."""

    if len(messages) <= _MAX_MESSAGES:
        return messages
    start = len(messages) - _MAX_MESSAGES
    while start < len(messages) and not isinstance(messages[start], HumanMessage):
        start += 1
    return messages[start:] if start < len(messages) else messages[-_MAX_MESSAGES:]


def save(session_id: str, messages: list[BaseMessage]) -> None:
    """Persist ``messages`` for ``session_id`` (system messages are not stored)."""

    cleaned = [m for m in messages if not isinstance(m, SystemMessage)]
    _store[session_id] = _trim(cleaned)


def clear(session_id: str) -> None:
    """Forget a session's history (used by the "New conversation" action)."""

    _store.pop(session_id, None)


def reset() -> None:
    """Drop all sessions (test helper)."""

    _store.clear()
