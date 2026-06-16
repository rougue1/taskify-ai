"""Natural-language due-date parsing for the agent tools.

Three strategies are tried in order:

1. An ISO fast-path (``datetime.fromisoformat``) — exact and cheap.
2. A small resolver for weekday / relative-week phrases that ``dateparser``
   does not handle ("next Friday", "this Monday", "end of next week",
   "next Monday at 9am").
3. ``dateparser`` itself for everything else it does handle well ("tomorrow",
   "in 3 days", "June 20", "06/20/2026").

If nothing can interpret the string, :func:`parse_due_date` raises ``ValueError``
so the caller (an agent tool) can surface a clean, actionable message instead of
silently storing garbage.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import dateparser

# Lean towards the upcoming occurrence for bare phrases and return naive
# datetimes (matching the resolver below and the historical parser).
_DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "RETURN_AS_TIMEZONE_AWARE": False,
}

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

# Optional trailing time, e.g. "at 9am", "at 17:30", "at 9".
_TIME_RE = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b")
_EDGE_OF_WEEK_RE = re.compile(
    r"(?:the\s+)?(end|start|beginning)\s+of\s+(this|next|the)\s+week"
)
_WEEKDAY_RE = re.compile(r"(?:(this|next|coming)\s+)?([a-z]+)")


def _extract_time(text: str) -> tuple[str, int | None, int | None]:
    """Pull an "at H[:MM][am|pm]" suffix out of ``text``; return (rest, hour, minute)."""

    match = _TIME_RE.search(text)
    if not match:
        return text, None, None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    hour = min(hour, 23)
    minute = min(minute, 59)
    cleaned = (text[: match.start()] + text[match.end() :]).strip()
    return cleaned, hour, minute


def _resolve_relative(text: str, base: datetime) -> datetime | None:
    """Resolve weekday / relative-week phrases. Return ``None`` if not recognized."""

    normalized = " ".join(text.lower().split())
    normalized, hour, minute = _extract_time(normalized)
    normalized = normalized.strip().rstrip(".")

    def finish(value: datetime) -> datetime:
        if hour is not None:
            return value.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return value

    if normalized == "today":
        return finish(base)
    if normalized in ("tomorrow", "tmrw", "tmr"):
        return finish(base + timedelta(days=1))
    if normalized == "yesterday":
        return finish(base - timedelta(days=1))

    edge = _EDGE_OF_WEEK_RE.fullmatch(normalized)
    if edge:
        which = edge.group(2)
        monday = base - timedelta(days=base.weekday())
        if which == "next":
            monday += timedelta(days=7)
        target = monday if edge.group(1) in ("start", "beginning") else monday + timedelta(days=6)
        return finish(target)

    if normalized == "next week":
        return finish(base + timedelta(days=7))
    if normalized == "this week":
        return finish(base)

    weekday = _WEEKDAY_RE.fullmatch(normalized)
    if weekday and weekday.group(2) in _WEEKDAYS:
        # All qualifiers (this/next/coming/bare) resolve to the next upcoming
        # occurrence of the weekday — never today — which matches common usage.
        delta = (_WEEKDAYS[weekday.group(2)] - base.weekday()) % 7 or 7
        return finish(base + timedelta(days=delta))

    return None


def parse_due_date(value: str | None, *, base: datetime | None = None) -> datetime | None:
    """Parse a due-date string (ISO or natural language) into a ``datetime``.

    ``base`` (defaulting to ``datetime.now()``) anchors relative expressions and
    is injectable for deterministic tests. Returns ``None`` for an empty value;
    raises ``ValueError`` when the string cannot be interpreted.
    """

    if not value:
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass

    resolved = _resolve_relative(text, base or datetime.now())
    if resolved is not None:
        return resolved

    parsed = dateparser.parse(text, settings=_DATEPARSER_SETTINGS)
    if parsed is not None:
        return parsed

    raise ValueError(
        f"Could not parse due_date '{value}'. Try an ISO date (2026-06-20), or a "
        "phrase like 'tomorrow', 'next Friday' or 'in 3 days'."
    )
