"""Unit tests for natural-language due-date parsing (no DB, no LLM).

Relative phrases are anchored to a fixed ``base`` so assertions are
deterministic; ``dateparser``-handled phrases use the real clock.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.agent.dates import parse_due_date

BASE = datetime(2026, 6, 16, 10, 0, 0)


def test_iso_passthrough():
    assert parse_due_date("2026-06-20").date() == date(2026, 6, 20)
    assert parse_due_date("2026-06-20T15:00").hour == 15


def test_next_weekday_lands_on_that_weekday():
    monday = parse_due_date("next Monday", base=BASE)
    assert monday.weekday() == 0
    assert monday > BASE
    assert parse_due_date("next Friday", base=BASE).weekday() == 4


def test_bare_and_qualified_weekdays():
    assert parse_due_date("friday", base=BASE).weekday() == 4
    assert parse_due_date("this Wednesday", base=BASE).weekday() == 2
    assert parse_due_date("coming sun", base=BASE).weekday() == 6


def test_weekday_with_time_suffix():
    dt = parse_due_date("next Monday at 9am", base=BASE)
    assert dt.weekday() == 0 and dt.hour == 9 and dt.minute == 0
    assert parse_due_date("friday at 5pm", base=BASE).hour == 17
    assert parse_due_date("monday at 17:30", base=BASE).minute == 30


def test_today_tomorrow_yesterday():
    assert parse_due_date("today", base=BASE).date() == BASE.date()
    assert parse_due_date("tomorrow", base=BASE).date() == (BASE + timedelta(days=1)).date()
    assert parse_due_date("yesterday", base=BASE).date() == (BASE - timedelta(days=1)).date()


def test_end_of_next_week_is_sunday_of_the_following_week():
    dt = parse_due_date("end of next week", base=BASE)
    assert dt.weekday() == 6  # Sunday
    assert dt > BASE + timedelta(days=6)


def test_relative_days_via_dateparser():
    dt = parse_due_date("in 3 days")
    assert (dt.date() - date.today()).days == 3


def test_empty_is_none():
    assert parse_due_date("") is None
    assert parse_due_date(None) is None


def test_unparseable_raises():
    with pytest.raises(ValueError):
        parse_due_date("definitely not a date")
