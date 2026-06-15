"""Per-request user context for the agent tools.

The authenticated user's id is injected into a :class:`contextvars.ContextVar`
before the graph runs, so tools can scope their database work to that user
*without* exposing ``user_id`` as an LLM-visible tool argument. ``contextvars``
values are copied into the tasks LangGraph spawns for tool execution, so reads
inside the tools see the value set here.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_current_user_id: ContextVar[int | None] = ContextVar("taskify_current_user_id", default=None)


def get_current_user_id() -> int | None:
    """Return the user id bound to the current async context, if any."""

    return _current_user_id.get()


@contextmanager
def user_context(user_id: int | None) -> Iterator[None]:
    """Bind ``user_id`` for the duration of the block, then restore the prior value."""

    token = _current_user_id.set(user_id)
    try:
        yield
    finally:
        _current_user_id.reset(token)
