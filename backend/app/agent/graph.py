"""LangGraph agent graph.

Implements the canonical ReAct-style loop with a ``ToolNode``:

    START -> agent -> (tool_calls?) -> tools -> agent -> ... -> END

The compiled graph is cached so the LLM/tool binding is built once per process.
A checkpointer is intentionally omitted for v0.1; conversation persistence is a
later milestone.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.tools import TOOLS
from app.config import settings


def _build_llm() -> ChatOllama:
    """Create the tool-calling chat model bound to the agent's tools."""

    llm = ChatOllama(
        model=settings.OLLAMA_TOOL_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.0,
    )
    return llm.bind_tools(TOOLS)


def build_graph():
    """Build and compile the LangGraph state graph."""

    llm = _build_llm()

    async def agent_node(state: MessagesState) -> dict:
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> str:
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return END

    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=None)


@lru_cache(maxsize=1)
def get_graph():
    """Return the process-wide compiled agent graph."""

    return build_graph()
