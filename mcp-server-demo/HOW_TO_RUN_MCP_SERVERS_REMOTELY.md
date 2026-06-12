# How to Run MCP Servers Remotely with Streamable HTTP

This guide explains how to expose your MCP server over HTTP so it can be reached
from remote clients and other projects using the `streamable_http` transport.
All examples match this repository's actual `main.py`, which is built with the
official Python SDK's `FastMCP`.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [How This Server Supports HTTP](#how-this-server-supports-http)
4. [Running the Server](#running-the-server)
5. [Connecting from a Client](#connecting-from-a-client)
6. [Examples](#examples)
7. [Remote Deployment](#remote-deployment)
8. [Troubleshooting](#troubleshooting)
9. [Security Best Practices](#security-best-practices)

## Overview

By default, MCP servers run on `stdio` (standard input/output), which only works
when the client spawns the server as a child process. To make your server
reachable over a network, run it with the `streamable-http` transport instead.

| Transport | How it works | Use when |
|-----------|--------------|----------|
| `stdio` | Client launches the server process and talks over stdin/stdout | Single local client; same machine; simple process management |
| `streamable-http` | Server runs as a standalone HTTP service; clients connect via URL | Standalone/shared service; multiple clients; network/remote access |

With `streamable-http`, this server listens at:

```
http://<host>:<port>/mcp      (default: http://127.0.0.1:8000/mcp)
```

> ⚠️ The endpoint path is **`/mcp`**. Clients must include it in the URL — pointing
> at `http://host:8000` without `/mcp` will fail to connect.

## Prerequisites

1. **Python 3.11+** and the [`uv`](https://docs.astral.sh/uv/) package manager
2. **Dependencies** (already declared in `pyproject.toml`):
   ```bash
   uv sync
   ```
   This installs `mcp[cli]`, `python-dotenv`, `requests`, and the LangChain MCP adapters.
3. **Environment variables** (optional — only for the tools that need them), in `.env`:
   ```bash
   OPENWEATHERMAP_API_KEY=your_key_here
   ```

## How This Server Supports HTTP

No code changes are needed — `main.py` already selects the transport from the
first CLI argument. The relevant parts:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo-weather-math-server")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

# ... subtract, get_weather, the greeting resource, and the greet_user prompt ...

if __name__ == "__main__":
    # python main.py        -> stdio
    # python main.py http   -> streamable-http on http://127.0.0.1:8000/mcp
    choice = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    transport = "streamable-http" if choice in ("http", "streamable-http") else "stdio"
    mcp.run(transport=transport)
```

### Changing the host and port

`FastMCP` reads its network settings from `FASTMCP_*` environment variables
(defaults: host `127.0.0.1`, port `8000`, path `/mcp`):

```bash
FASTMCP_HOST=0.0.0.0 FASTMCP_PORT=9000 uv run python main.py http
# -> http://0.0.0.0:9000/mcp
```

Equivalently, you can set them in code when constructing the server:

```python
mcp = FastMCP("demo-weather-math-server", host="0.0.0.0", port=9000)
```

Bind to `0.0.0.0` to accept connections from other machines on your network.

## Running the Server

```bash
# stdio (default)
uv run python main.py

# streamable-http on http://127.0.0.1:8000/mcp
uv run python main.py http
```

Expected output:

```
MCP Server is starting...
Transport: streamable-http (http://127.0.0.1:8000/mcp)
Registered Tools: add, subtract, get_weather
Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Quick reachability check

A streamable-http server requires both JSON and SSE in the `Accept` header:

```bash
curl -i -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
```

A `200 OK` means the server is ready for clients.

## Connecting from a Client

The URL to give any client is **`http://<host>:<port>/mcp`**.

### Using langchain-mcp-adapters

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "demo": {
        "transport": "streamable_http",
        "url": "http://127.0.0.1:8000/mcp",
        # "headers": {"Authorization": "Bearer YOUR_TOKEN"},  # if you add auth
    }
})

# Load all tools across configured servers
tools = await client.get_tools()
print(f"Loaded {len(tools)} tools")
```

### Using the raw MCP Python SDK

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://127.0.0.1:8000/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        result = await session.call_tool("add", {"a": 2, "b": 3})
        print(result)
```

### Using Claude Code

```bash
claude mcp add --transport http demo http://127.0.0.1:8000/mcp
```

### Generic JSON config (Cursor / Claude Desktop-style)

```json
{
  "mcpServers": {
    "demo": { "type": "streamable-http", "url": "http://127.0.0.1:8000/mcp" }
  }
}
```

> **Docker/containers:** `127.0.0.1` resolves to the container itself. To reach a
> server running on the host, use `http://host.docker.internal:8000/mcp`.

## Examples

### Example 1: Local server, LangChain client

**Terminal 1 — start the server:**
```bash
uv run python main.py http
```

**Terminal 2 — connect and call a tool:**
```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    client = MultiServerMCPClient({
        "demo": {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp"}
    })
    tools = await client.get_tools()
    print("Available tools:", [t.name for t in tools])

asyncio.run(main())
```

### Example 2: Combining this server with a remote one

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "local-demo": {
        "transport": "streamable_http",
        "url": "http://127.0.0.1:8000/mcp",
    },
    "remote-tavily": {
        "transport": "streamable_http",
        "url": "https://mcp.tavily.com/mcp/?tavilyApiKey=YOUR_KEY",
    },
})

tools = await client.get_tools()  # tools from both servers, merged
```

## Remote Deployment

### Run as a service (systemd on Linux)

```bash
# /etc/systemd/system/mcp-server.service
[Unit]
Description=MCP Demo Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/mcp-server-demo
Environment=FASTMCP_HOST=0.0.0.0
Environment=FASTMCP_PORT=8000
EnvironmentFile=/home/ubuntu/mcp-server-demo/.env
ExecStart=/home/ubuntu/.local/bin/uv run python main.py http
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now mcp-server
```

### Put it behind nginx + HTTPS

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # Streamable HTTP uses SSE for streaming responses:
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
```

```bash
sudo certbot --nginx -d your-domain.com
```

Clients then connect to `https://your-domain.com/mcp`.

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py ./

ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000
EXPOSE 8000

CMD ["uv", "run", "python", "main.py", "http"]
```

```bash
docker build -t mcp-server-demo .
docker run -p 8000:8000 -e OPENWEATHERMAP_API_KEY=your_key mcp-server-demo
# Reachable at http://localhost:8000/mcp from the host
```

## Troubleshooting

### `Address already in use`

```bash
lsof -i :8000          # find the process holding the port
kill -9 <PID>          # stop it
# or just run on another port:
FASTMCP_PORT=9000 uv run python main.py http
```

### Client connects to the wrong path

The most common mistake is omitting `/mcp`. The URL must be
`http://host:8000/mcp`, not `http://host:8000`.

### `406 Not Acceptable` when testing with curl

Streamable HTTP requires the client to accept SSE. Include both content types:

```
Accept: application/json, text/event-stream
```

### Can't reach the server from another machine

By default the server binds to `127.0.0.1` (localhost only). Start it with
`FASTMCP_HOST=0.0.0.0` and make sure the port is open in your firewall/security group.

### `get_weather` returns an API-key error

Set `OPENWEATHERMAP_API_KEY` in `.env` (or pass `api_key` as a tool argument).
New OpenWeatherMap keys can take up to 2 hours to activate.

## Security Best Practices

✅ **Do:**
- Use HTTPS/TLS in production (terminate at nginx or a load balancer)
- Add an authentication layer (e.g. a bearer token / reverse-proxy auth) before exposing publicly
- Keep API keys in `.env` / secrets, never in code
- Bind to `127.0.0.1` unless you intentionally need network access
- Monitor logs and apply rate limiting on public endpoints

❌ **Don't:**
- Expose `0.0.0.0` to the internet without auth and TLS
- Commit `.env` or secrets to git
- Run the service as root
