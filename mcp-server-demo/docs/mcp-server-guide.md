# Building an MCP Server with Python

A comprehensive guide to creating a Model Context Protocol (MCP) server with
tools, resources, and prompts — using the official Python SDK's `FastMCP`.
The code here matches this repository's `main.py`.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Project Setup](#project-setup)
- [Getting OpenWeatherMap API Key](#getting-openweathermap-api-key)
- [Building the Server](#building-the-server)
- [Running the Server](#running-the-server)
- [Testing Your Server](#testing-your-server)
- [Connecting to Claude Desktop (stdio)](#connecting-to-claude-desktop-stdio)
- [Connecting over HTTP (remote clients)](#connecting-over-http-remote-clients)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.11 or higher
- `uv` package manager ([install from here](https://docs.astral.sh/uv/))
- OpenWeatherMap API key (free tier — only needed for the weather tool)

## Project Setup

### 1. Initialize the Project

```bash
uv init mcp-server-demo
cd mcp-server-demo
```

### 2. Install Dependencies

```bash
# Core MCP SDK (with the CLI / Inspector), plus the libraries the tools use
uv add "mcp[cli]" python-dotenv requests

# For writing MCP *clients* with LangChain (optional)
uv add langchain langchain-openai langchain-mcp-adapters
```

Or, if you already have the `pyproject.toml` from this repo:

```bash
uv sync
```

### 3. Create Environment File

```bash
touch .env
```

Add your OpenWeatherMap API key (we'll get this in the next section):

```
OPENWEATHERMAP_API_KEY=your_api_key_here
```

**Important:** Add `.env` to your `.gitignore` to avoid committing secrets:

```bash
echo ".env" >> .gitignore
```

## Getting OpenWeatherMap API Key

### Step 1: Sign Up

1. Go to [OpenWeatherMap](https://openweathermap.org/)
2. Click "Sign Up" in the top right corner
3. Fill in your email, username, and password
4. Verify your email address

### Step 2: Get Your API Key

1. Log in to your OpenWeatherMap account
2. Navigate to "API keys" (under your profile/username dropdown)
3. Copy the default API key and paste it into your `.env` file

**Note:** New API keys can take up to 2 hours to activate. If you get
authentication errors initially, wait a bit and try again.

### Free Tier Limits

- 60 calls per minute
- 1,000,000 calls per month
- Current weather data + 5-day forecast (3-hour intervals)
- 200,000+ cities worldwide

## Building the Server

Create `main.py` in your project root. We use `FastMCP`, which turns plain
decorated functions into MCP tools, resources, and prompts:

```python
import sys
import os
from mcp.server.fastmcp import FastMCP
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Create an MCP server
mcp = FastMCP("demo-weather-math-server")

# ============================================
# MATH TOOLS
# ============================================

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    return a - b


# ============================================
# WEATHER TOOL
# ============================================

@mcp.tool()
def get_weather(city: str, api_key: str | None = None) -> str:
    """Get current weather for a city using the OpenWeatherMap API.

    Args:
        city: Name of the city (e.g., 'London', 'New York', 'Tokyo').
        api_key: OpenWeatherMap API key. Falls back to the
            OPENWEATHERMAP_API_KEY environment variable if not provided.
    """
    api_key = api_key or os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        return (
            "Error: OpenWeatherMap API key not provided. Pass the api_key "
            "parameter or set the OPENWEATHERMAP_API_KEY environment variable."
        )

    try:
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": api_key, "units": "metric"}  # Celsius

        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"]
        wind_speed = data["wind"]["speed"]

        return f"""Weather in {city.title()}:
            🌡️ Temperature: {temp}°C (feels like {feels_like}°C)
            💧 Humidity: {humidity}%
            🌤️ Conditions: {description.capitalize()}
            💨 Wind Speed: {wind_speed} m/s"""

    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return f"Error: City '{city}' not found"
        elif response.status_code == 401:
            return "Error: Invalid API key. Please check your OPENWEATHERMAP_API_KEY"
        return f"Error: HTTP {response.status_code} - {str(e)}"
    except Exception as e:
        return f"Error fetching weather data: {str(e)}"


# ============================================
# GREETING RESOURCE
# ============================================

@mcp.resource("greeting://default")
def default_greeting() -> str:
    """A default greeting message."""
    return "Hello! Welcome to the MCP Demo Server!"


# ============================================
# GREETING PROMPT
# ============================================

@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Generate a greeting with different styles.

    Args:
        name: The person's name to greet.
        style: The style of greeting - 'friendly', 'formal', or 'casual'.
    """
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
        "casual": "Please write a casual, relaxed greeting",
    }
    style_instruction = styles.get(style, styles["friendly"])
    return f"{style_instruction} for someone named {name}."


# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    # python main.py        -> stdio  (Claude Desktop, `uv run mcp dev main.py`)
    # python main.py http   -> streamable-http on http://127.0.0.1:8000/mcp
    choice = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    transport = "streamable-http" if choice in ("http", "streamable-http") else "stdio"
    mcp.run(transport=transport)
```

> 💡 **Resources can be parameterized too.** This example uses a static
> `greeting://default`, but you can capture path parameters:
> `@mcp.resource("greeting://{name}")` with a matching `def get_greeting(name: str)`.

## Running the Server

The transport is selected by the first CLI argument:

```bash
# stdio (default)
uv run python main.py

# streamable-http on http://127.0.0.1:8000/mcp
uv run python main.py http
```

## Testing Your Server

### Method 1: MCP Inspector (Best for Development)

The Inspector provides a web interface to exercise your server:

```bash
uv run mcp dev main.py
```

This opens a web UI (default `http://127.0.0.1:6274`) where you can:
- Test `add` and `subtract` with different inputs
- Try `get_weather` with different cities
- Read the `greeting://default` resource
- Preview the `greet_user` prompt with different styles

### Method 2: Direct Run

```bash
uv run python main.py        # stdio
uv run python main.py http   # HTTP — then connect a client (see below)
```

### Testing Individual Tools

**Math tools:**
```json
{ "name": "add", "arguments": { "a": 10, "b": 25 } }
```

**Weather tool:**
```json
{ "name": "get_weather", "arguments": { "city": "Chennai" } }
```

**Greeting prompt:**
```json
{ "name": "greet_user", "arguments": { "name": "Sarah", "style": "formal" } }
```

## Connecting to Claude Desktop (stdio)

### macOS Configuration

1. Open the Claude Desktop config:
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

2. Add your server (stdio — Claude Desktop launches it for you):
```json
{
  "mcpServers": {
    "demo-server": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/full/path/to/your/mcp-server-demo",
        "python",
        "main.py"
      ],
      "env": {
        "OPENWEATHERMAP_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Windows Configuration

Open `%APPDATA%\Claude\claude_desktop_config.json` and add the same
configuration (adjust the path format for Windows).

### Restart Claude Desktop

After saving, **completely quit and restart Claude Desktop**.

### Using Your Server in Claude

Once connected, ask things like:
- "Add 45 and 67"
- "What's the weather in London?"
- "Subtract 30 from 100"
- "Give me a formal greeting for Dr. Smith"

Claude will automatically call your MCP tools to answer.

## Connecting over HTTP (remote clients)

To let other projects connect over the network, run the server with the HTTP
transport and point clients at `http://127.0.0.1:8000/mcp`:

```bash
uv run python main.py http
```

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient({
    "demo": {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp"}
})
tools = await client.get_tools()
```

See [`HOW_TO_RUN_MCP_SERVERS_REMOTELY.md`](../HOW_TO_RUN_MCP_SERVERS_REMOTELY.md)
for binding to `0.0.0.0`, Docker, systemd, nginx/HTTPS, and more client examples.

## Troubleshooting

**1. `ModuleNotFoundError: No module named 'mcp'` (or `mcp.server.fastmcp`)**

Install the SDK with the CLI extra and run through `uv`:
```bash
uv add "mcp[cli]"
uv run python main.py
```

**2. `Error: Invalid API key`**

- Verify the key in `.env` (the variable name is `OPENWEATHERMAP_API_KEY`)
- New keys take up to 2 hours to activate — wait and retry
- Ensure `.env` is in the same directory you run `main.py` from

**3. `City not found`**

- Add a country code: `"London,GB"` instead of `"London"`
- Check spelling; some very small cities aren't in the database

**4. Wrong Python / syntax errors when running `python main.py`**

Always use `uv run` so the project's virtualenv is used:
```bash
uv run python main.py   # ✅ correct
python main.py          # ❌ may use the wrong interpreter
```

**5. Claude Desktop doesn't show the server**

- Use an absolute path in `claude_desktop_config.json`
- Completely quit and restart Claude Desktop
- Validate the JSON syntax
- Check the logs (below)

### Checking Logs

**macOS:**
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Windows:**
```powershell
Get-Content "$env:APPDATA\Claude\logs\mcp*.log" -Wait
```

## Next Steps

1. **Add more tools** — wrap any function with `@mcp.tool()`
2. **Integrate more APIs** — news, stocks, databases, etc.
3. **Add authentication** — protect sensitive operations / public endpoints
4. **Add dynamic resources** — parameterized `@mcp.resource("scheme://{id}")`
5. **Deploy remotely** — see the HTTP guide for systemd / Docker / nginx

## Resources

- [MCP Official Documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk)
- [OpenWeatherMap API Docs](https://openweathermap.org/api)
- [uv Documentation](https://docs.astral.sh/uv/)

---

**Built with ❤️ by Arun**

*Last Updated: June 2026*
