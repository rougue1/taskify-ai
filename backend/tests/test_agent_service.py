"""Tests for the agent orchestration layer using a fake graph (no LLM).

These cover the v0.3/v0.4 contract: history reconstruction, server-side session
memory, recursion handling, <think> stripping, and SSE stream events.
"""

from __future__ import annotations

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.errors import GraphRecursionError

from app.agent import sessions
from app.services import agent_service


class FakeGraph:
    """Records the messages passed to it and appends a canned AI reply."""

    def __init__(self, replies: list[str]):
        self.replies = replies
        self.calls: list[list] = []
        self._index = 0

    async def ainvoke(self, state, config=None):
        self.calls.append(list(state["messages"]))
        reply = self.replies[min(self._index, len(self.replies) - 1)]
        self._index += 1
        return {"messages": [*state["messages"], AIMessage(content=reply)]}


class RecursionGraph:
    async def ainvoke(self, state, config=None):
        raise GraphRecursionError("too many steps")


class FakeStreamGraph:
    """Yields a canned astream_events sequence then a root on_chain_end."""

    def __init__(self, events):
        self._events = events

    async def astream_events(self, _input, config=None, **kwargs):
        for event in self._events:
            yield event


# --- History reconstruction ---------------------------------------------------


def test_to_lc_messages_reconstructs_roles():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    messages = agent_service._to_lc_messages(history)
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert messages[0].content == "hi"
    assert messages[1].content == "hello"


def test_to_lc_messages_strips_think_from_assistant():
    history = [{"role": "assistant", "content": "<think>secret</think>visible"}]
    messages = agent_service._to_lc_messages(history)
    assert messages[0].content == "visible"


def test_to_lc_messages_keeps_matched_tool_calls_and_results():
    history = [
        {"role": "user", "content": "search milk"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call_1", "name": "search_tasks", "args": {"query": "milk"}}],
        },
        {"role": "tool", "content": '{"count": 0}', "tool_call_id": "call_1"},
        {"role": "assistant", "content": "No milk tasks."},
    ]
    messages = agent_service._to_lc_messages(history)
    assert isinstance(messages[1], AIMessage)
    assert messages[1].tool_calls and messages[1].tool_calls[0]["id"] == "call_1"
    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == "call_1"


def test_to_lc_messages_drops_orphan_tool_calls_and_results():
    history = [
        {
            "role": "assistant",
            "content": "calling",
            "tool_calls": [{"id": "x", "name": "search_tasks", "args": {}}],
        },  # no matching tool result -> tool_calls dropped
        {"role": "tool", "content": "orphan", "tool_call_id": "y"},  # no matching call -> dropped
    ]
    messages = agent_service._to_lc_messages(history)
    assert len(messages) == 1
    assert isinstance(messages[0], AIMessage)
    assert not messages[0].tool_calls


# --- Session memory -----------------------------------------------------------


async def test_chat_returns_session_id(monkeypatch):
    monkeypatch.setattr(agent_service, "get_graph", lambda: FakeGraph(["hi there"]))
    result = await agent_service.chat("hello", user_id=1)
    assert result["session_id"]
    assert result["response"] == "hi there"


async def test_chat_remembers_history_across_turns(monkeypatch):
    fake = FakeGraph(["first reply", "second reply"])
    monkeypatch.setattr(agent_service, "get_graph", lambda: fake)

    first = await agent_service.chat("my name is Sam", user_id=1)
    sid = first["session_id"]
    await agent_service.chat("what is my name?", session_id=sid, user_id=1)

    # The second invocation must include the full prior conversation.
    second_call = fake.calls[1]
    contents = [m.content for m in second_call]
    assert "my name is Sam" in contents
    assert "first reply" in contents
    assert "what is my name?" in contents
    # System prompt is present exactly once at the front.
    assert isinstance(second_call[0], SystemMessage)
    assert sum(isinstance(m, SystemMessage) for m in second_call) == 1


async def test_chat_persists_history_in_session_store(monkeypatch):
    monkeypatch.setattr(agent_service, "get_graph", lambda: FakeGraph(["stored reply"]))
    result = await agent_service.chat("remember this", user_id=1)
    stored = sessions.get(result["session_id"])
    assert stored is not None
    assert any(isinstance(m, HumanMessage) and m.content == "remember this" for m in stored)
    # No system message is persisted in history.
    assert not any(isinstance(m, SystemMessage) for m in stored)


async def test_chat_strips_think_from_response_and_history(monkeypatch):
    monkeypatch.setattr(
        agent_service,
        "get_graph",
        lambda: FakeGraph(["<think>deliberating</think>The final answer"]),
    )
    result = await agent_service.chat("question", user_id=1)
    assert result["response"] == "The final answer"
    stored = sessions.get(result["session_id"])
    assert all("<think>" not in (m.content or "") for m in stored)


async def test_chat_handles_recursion_limit(monkeypatch):
    monkeypatch.setattr(agent_service, "get_graph", lambda: RecursionGraph())
    result = await agent_service.chat("loop forever", user_id=1)
    assert "too many steps" in result["response"]
    assert result["session_id"]


# --- Streaming ----------------------------------------------------------------


async def _collect(agen):
    return [event async for event in agen]


async def test_stream_emits_thinking_token_and_done(monkeypatch):
    final_messages = [HumanMessage(content="q"), AIMessage(content="Hello there")]
    events = [
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": AIMessageChunk(content="<think>reasoning</think>Hello there")},
        },
        {"event": "on_chain_end", "parent_ids": [], "data": {"output": {"messages": final_messages}}},
    ]
    monkeypatch.setattr(agent_service, "get_graph", lambda: FakeStreamGraph(events))

    collected = await _collect(agent_service.stream("hi", user_id=1))
    types = [etype for etype, _ in collected]

    assert types[0] == "session"
    assert "thinking" in types
    assert "token" in types
    assert types[-1] == "done"

    thinking = "".join(d["content"] for t, d in collected if t == "thinking")
    answer = "".join(d["content"] for t, d in collected if t == "token")
    done = next(d for t, d in collected if t == "done")
    assert thinking == "reasoning"
    assert answer == "Hello there"
    assert done["response"] == "Hello there"
    assert "<think>" not in done["response"]


async def test_stream_emits_tool_events(monkeypatch):
    final_messages = [AIMessage(content="Found them")]
    events = [
        {
            "event": "on_tool_start",
            "name": "search_tasks",
            "run_id": "r1",
            "data": {"input": {"query": "milk"}},
        },
        {"event": "on_tool_end", "name": "search_tasks", "run_id": "r1", "data": {"output": "{}"}},
        {
            "event": "on_chat_model_stream",
            "data": {"chunk": AIMessageChunk(content="Found them")},
        },
        {"event": "on_chain_end", "parent_ids": [], "data": {"output": {"messages": final_messages}}},
    ]
    monkeypatch.setattr(agent_service, "get_graph", lambda: FakeStreamGraph(events))

    collected = await _collect(agent_service.stream("find milk", user_id=1))
    tool_starts = [d for t, d in collected if t == "tool_start"]
    assert tool_starts and tool_starts[0]["name"] == "search_tasks"
    assert any(t == "tool_end" for t, _ in collected)


async def test_stream_reports_errors(monkeypatch):
    class Boom:
        async def astream_events(self, _input, config=None, **kwargs):
            raise RuntimeError("ollama down")
            yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(agent_service, "get_graph", lambda: Boom())
    collected = await _collect(agent_service.stream("hi", user_id=1))
    assert any(t == "error" for t, _ in collected)
