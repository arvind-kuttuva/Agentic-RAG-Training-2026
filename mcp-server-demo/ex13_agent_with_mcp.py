# LangGraph Agent backed by an MCP Server
#
# This example is the same agent loop as ex8 (LLM <-> ToolNode),
# BUT the tools are NOT defined locally. They are discovered at
# runtime from a remote MCP (Model Context Protocol) server.
#
# MCP server (already running separately):
#   Name      : demo-weather-math-server
#   URL       : http://127.0.0.1:8000/mcp
#   Transport : streamable-http
#   Auth      : none
#   Tools     : add, subtract, get_weather
#
# We only write the CLIENT logic here. langchain-mcp-adapters turns
# the MCP tools into normal LangChain tools, so the rest of the graph
# looks exactly like a regular tool-calling agent.
#
# Requires: uv add langchain-mcp-adapters

import asyncio

from typing import TypedDict, Annotated, List

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()


# =========================
# 1. LLM
# =========================
llm = ChatOpenAI(model="gpt-5.4")


# =========================
# 2. State
# =========================
class AgentState(TypedDict):
    messages: Annotated[List, add_messages]


# =========================
# 3. MCP Client
# =========================
# One client can talk to many MCP servers. We register just one here.
# The key ("demo-weather-math-server") is a local label for the connection.
mcp_client = MultiServerMCPClient(
    {
        "demo-weather-math-server": {
            "url": "http://127.0.0.1:8000/mcp",
            "transport": "streamable_http",
        }
    }
)


# =========================
# 4. Build Graph
# =========================
# get_tools() is async (it connects to the server and lists its tools),
# so the whole setup lives inside an async function.
async def build_app():
    # Discover tools exposed by the MCP server (add, subtract, get_weather).
    tools = await mcp_client.get_tools()

    print("\n🔌 Tools discovered from MCP server:")
    for t in tools:
        print(f"   - {t.name}: {t.description}")

    # Bind the remote tools to the LLM exactly like local tools.
    llm_with_tools = llm.bind_tools(tools)

    # Agent node (LLM only) — decides whether to call a tool.
    def agent_node(state: AgentState):
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    # Conditional routing: tool call -> tools, otherwise finish.
    def should_continue(state: AgentState):
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tools"
        return END

    # Prebuilt ToolNode runs the MCP tools (they are async-capable).
    tool_node = ToolNode(tools)

    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, ["tools", END])
    workflow.add_edge("tools", "agent")

    app = workflow.compile()

    # Save the graph visualization.
    graph_image = app.get_graph().draw_mermaid_png()
    with open("examples/ex13_agent_with_mcp.png", "wb") as f:
        f.write(graph_image)

    return app


# =========================
# 5. Run Example
# =========================
async def main():
    app = await build_app()

    # Use ainvoke so the async MCP tools can run.
    result = await app.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "What is the weather in Chennai, and what is 25 + 17?",
                }
            ]
        }
    )

    print("\nFinal Answer:\n")
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
