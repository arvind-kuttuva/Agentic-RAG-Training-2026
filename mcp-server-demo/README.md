# MCP Server Demo — Weather & Math

A small Model Context Protocol (MCP) server built with the official Python SDK
(`FastMCP`). It demonstrates all three MCP building blocks — **tools**,
**resources**, and **prompts** — and can be exposed over two transports:

- **`stdio`** — the client spawns the server as a child process (Claude Desktop, `uv run mcp dev`)
- **`streamable-http`** — the server runs as a standalone HTTP service that any client connects to over the network

> Full remote/HTTP guide: [`HOW_TO_RUN_MCP_SERVERS_REMOTELY.md`](./HOW_TO_RUN_MCP_SERVERS_REMOTELY.md)

## What the server exposes

| Type | Name | Description |
|------|------|-------------|
| Tool | `add(a, b)` | Add two numbers |
| Tool | `subtract(a, b)` | Subtract `b` from `a` |
| Tool | `get_weather(city, api_key?)` | Current weather via OpenWeatherMap |
| Resource | `greeting://default` | A static greeting message |
| Prompt | `greet_user(name, style)` | Generates a greeting prompt (`friendly` / `formal` / `casual`) |

Server name: **`demo-weather-math-server`**

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) package manager
- (Optional) An [OpenWeatherMap API key](https://openweathermap.org/api) — only needed for `get_weather`

## Setup

```bash
# Install dependencies (creates the .venv automatically)
uv sync

# Optional: provide the weather API key
echo "OPENWEATHERMAP_API_KEY=your_key_here" >> .env
```

> `add` and `subtract` work with no configuration. `get_weather` falls back to the
> `OPENWEATHERMAP_API_KEY` environment variable, or you can pass `api_key` as a tool argument.

## Running the server

The transport is chosen by the first CLI argument:

```bash
# stdio (default) — for Claude Desktop / local clients
uv run python main.py

# streamable-http — standalone service on http://127.0.0.1:8000/mcp
uv run python main.py http
```

When running over HTTP you'll see:

```
Transport: streamable-http (http://127.0.0.1:8000/mcp)
Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Bind to a different host/port

`FastMCP` reads `FASTMCP_HOST` / `FASTMCP_PORT` (defaults `127.0.0.1` / `8000`):

```bash
FASTMCP_HOST=0.0.0.0 FASTMCP_PORT=9000 uv run python main.py http
# -> http://0.0.0.0:9000/mcp
```

Use `0.0.0.0` to accept connections from other machines on your network.

## Connecting a client (streamable-http)

The endpoint is **`http://127.0.0.1:8000/mcp`** — note the `/mcp` path.

**LangChain / LangGraph** (`langchain-mcp-adapters`):

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "demo": {
        "transport": "streamable_http",
        "url": "http://127.0.0.1:8000/mcp",
    }
})
tools = await client.get_tools()
```

**Claude Code:**

```bash
claude mcp add --transport http demo http://127.0.0.1:8000/mcp
```

**Generic JSON config** (Cursor / Claude Desktop-style):

```json
{
  "mcpServers": {
    "demo": { "type": "streamable-http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

> Connecting from Docker/another container? `127.0.0.1` points at the container
> itself — use `http://host.docker.internal:8000/mcp` to reach the host.

## Testing with the MCP Inspector

```bash
uv run mcp dev main.py
```

Opens a web UI (default `http://127.0.0.1:6274`) to interactively call the tools,
read the `greeting://default` resource, and preview the `greet_user` prompt.

---

## Course notes: MCP concepts

### Disadvantages of MCP
1. More token consumption
2. Similar tools can lead agents to pick the wrong one (fixable with good naming/descriptions)
3. Prompt injection risk (partially mitigable by AI engineers)
4. Higher spend, largely driven by the extra token consumption

### MCP server development
- Exposed over transport layers such as `stdio` or `streamable-http`
- Can provide three things: **Tools**, **Resources**, **Prompts**
- Can be written in Python, TypeScript, and many other languages
- MCP servers come in three flavours:
  1. Official servers (GitHub, Jira, HubSpot, Tavily, Exa)
  2. Community / unofficial servers (Google Drive, Google Maps)
  3. Your own private servers (like this demo)

### MCP clients
- Can be built in any language and connect over the chosen transport
- Examples: GitHub Copilot, Claude Code, and frameworks like LangChain / LangGraph / AutoGen / CrewAI / Agno / Vercel AI SDK
