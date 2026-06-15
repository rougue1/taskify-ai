"""Parsing of ``<think>...</think>`` reasoning blocks emitted by qwen3.5:9b.

Two consumers:

* :func:`strip_think` — used on a *complete* message before it is stored in
  history or returned from ``/chat``; reasoning must never leak into the answer.
* :class:`ThinkStreamParser` — a small state machine that classifies an
  incremental token stream into ``thinking`` vs ``answer`` segments, correctly
  handling tags that straddle chunk boundaries (e.g. a chunk ending in ``"<thi"``).
"""

from __future__ import annotations

import re

OPEN_TAG = "<think>"
CLOSE_TAG = "</think>"

# A complete <think>...</think> block (non-greedy, across newlines).
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
# An unclosed <think> running to the end of the text.
_OPEN_THINK_RE = re.compile(r"<think>.*$", re.DOTALL)


def strip_think(text: str | None) -> str:
    """Remove all reasoning blocks from ``text`` and return the clean answer."""

    if not text:
        return ""
    cleaned = _THINK_BLOCK_RE.sub("", text)
    cleaned = _OPEN_THINK_RE.sub("", cleaned)
    cleaned = cleaned.replace(CLOSE_TAG, "")
    return cleaned.strip()


def _partial_tag_holdback(text: str, tag: str) -> int:
    """Length of the longest suffix of ``text`` that is a prefix of ``tag``.

    That suffix might be the start of a real tag split across chunks, so it is
    held back from emission until more text arrives.
    """

    for length in range(min(len(text), len(tag) - 1), 0, -1):
        if tag.startswith(text[-length:]):
            return length
    return 0


class ThinkStreamParser:
    """Incrementally split a token stream into ``thinking`` / ``answer`` parts.

    ``feed`` returns a list of ``(kind, text)`` tuples where ``kind`` is either
    ``"thinking"`` or ``"answer"``. Call ``flush`` once the stream ends to drain
    any buffered text.
    """

    def __init__(self) -> None:
        self._pending = ""
        self._in_think = False
        self.saw_think = False  # True once any thinking content has been seen

    def feed(self, text: str) -> list[tuple[str, str]]:
        """Consume a chunk of streamed text and return classified segments."""

        if not text:
            return []
        events: list[tuple[str, str]] = []
        self._pending += text

        while self._pending:
            target = CLOSE_TAG if self._in_think else OPEN_TAG
            kind = "thinking" if self._in_think else "answer"
            idx = self._pending.find(target)

            if idx != -1:
                if idx > 0:
                    events.append((kind, self._pending[:idx]))
                    if self._in_think:
                        self.saw_think = True
                self._pending = self._pending[idx + len(target) :]
                self._in_think = not self._in_think
                if self._in_think:
                    self.saw_think = True
                continue

            holdback = _partial_tag_holdback(self._pending, target)
            emit = self._pending[: len(self._pending) - holdback]
            if emit:
                events.append((kind, emit))
                if self._in_think:
                    self.saw_think = True
            self._pending = self._pending[len(self._pending) - holdback :]
            break

        return events

    def flush(self) -> list[tuple[str, str]]:
        """Return any remaining buffered text once the stream has ended."""

        if not self._pending:
            return []
        kind = "thinking" if self._in_think else "answer"
        if self._in_think:
            self.saw_think = True
        remainder = self._pending
        self._pending = ""
        return [(kind, remainder)]
