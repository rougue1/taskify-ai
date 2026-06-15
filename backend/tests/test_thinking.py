"""Tests for <think> reasoning parsing and stripping."""

from __future__ import annotations

from app.agent.thinking import ThinkStreamParser, strip_think


def _drain(parser: ThinkStreamParser, chunks: list[str]) -> tuple[str, str]:
    """Feed chunks through the parser and return (thinking, answer) text."""

    thinking, answer = [], []
    for chunk in chunks:
        for kind, text in parser.feed(chunk):
            (thinking if kind == "thinking" else answer).append(text)
    for kind, text in parser.flush():
        (thinking if kind == "thinking" else answer).append(text)
    return "".join(thinking), "".join(answer)


def test_strip_think_removes_complete_block():
    assert strip_think("<think>reasoning here</think>The answer") == "The answer"


def test_strip_think_removes_multiline_block():
    text = "<think>line one\nline two</think>\nFinal answer"
    assert strip_think(text) == "Final answer"


def test_strip_think_handles_unclosed_block():
    assert strip_think("Partial answer <think>still thinking...") == "Partial answer"


def test_strip_think_no_think_is_unchanged():
    assert strip_think("Just a plain answer") == "Just a plain answer"


def test_parser_separates_thinking_from_answer():
    thinking, answer = _drain(ThinkStreamParser(), ["<think>reasoning</think>Hello world"])
    assert thinking == "reasoning"
    assert answer == "Hello world"


def test_parser_handles_tag_split_across_chunks():
    # The opening tag is split across three chunks, as can happen token-by-token.
    chunks = ["<", "thi", "nk>secret", " reasoning</thi", "nk>Visible answer"]
    thinking, answer = _drain(ThinkStreamParser(), chunks)
    assert thinking == "secret reasoning"
    assert answer == "Visible answer"
    assert "<think>" not in answer and "think" not in answer


def test_parser_token_by_token_streaming():
    full = "<think>abc</think>xyz"
    thinking, answer = _drain(ThinkStreamParser(), list(full))
    assert thinking == "abc"
    assert answer == "xyz"


def test_parser_reports_no_think_when_absent():
    parser = ThinkStreamParser()
    _drain(parser, ["plain answer with no reasoning"])
    assert parser.saw_think is False


def test_parser_reports_saw_think_when_present():
    parser = ThinkStreamParser()
    _drain(parser, ["<think>x</think>y"])
    assert parser.saw_think is True
