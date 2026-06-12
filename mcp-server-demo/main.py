import sys
import os
import logging
from mcp.server.fastmcp import FastMCP
import requests
from dotenv import load_dotenv

# Configure logging to stderr (since stdout is used for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# Load environment variables
load_dotenv()

logger.info("Starting MCP Demo Server...")

# Create an MCP server
mcp = FastMCP("demo-weather-math-server")
logger.info("MCP Server instance created: Demo Weather & Math Server")


# ============================================
# MATH TOOLS
# ============================================


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    result = a + b
    logger.info(f"Tool 'add' called with a={a}, b={b}, returning: {result}")
    return result


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract b from a."""
    result = a - b
    logger.info(f"Tool 'subtract' called with a={a}, b={b}, returning: {result}")
    return result


@mcp.tool()
def get_weather(city: str, api_key: str | None = None) -> str:
    """Get current weather for a city using the OpenWeatherMap API.

    Args:
        city: Name of the city (e.g., 'London', 'New York', 'Tokyo').
        api_key: OpenWeatherMap API key. Falls back to the
            OPENWEATHERMAP_API_KEY environment variable if not provided.
    """
    logger.info(f"Tool 'get_weather' called for city: {city}")

    api_key = api_key or os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        logger.warning("OpenWeatherMap API key not provided")
        return (
            "Error: OpenWeatherMap API key not provided. Pass the api_key "
            "parameter or set the OPENWEATHERMAP_API_KEY environment variable."
        )

    try:
        # Build API URL
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": api_key, "units": "metric"}  # Use Celsius

        # Make API request
        response = requests.get(base_url, params=params)
        response.raise_for_status()

        # Parse response
        data = response.json()

        # Extract weather information
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"]
        wind_speed = data["wind"]["speed"]

        # Format response
        weather_info = f"""Weather in {city.title()}:
            🌡️ Temperature: {temp}°C (feels like {feels_like}°C)
            💧 Humidity: {humidity}%
            🌤️ Conditions: {description.capitalize()}
            💨 Wind Speed: {wind_speed} m/s"""

        logger.info(f"Successfully fetched weather for {city}")
        return weather_info

    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            logger.error(f"City '{city}' not found")
            return f"Error: City '{city}' not found"
        elif response.status_code == 401:
            logger.error("Invalid API key")
            return "Error: Invalid API key. Please check your OPENWEATHERMAP_API_KEY"
        else:
            logger.error(f"HTTP {response.status_code} - {str(e)}")
            return f"Error: HTTP {response.status_code} - {str(e)}"
    except Exception as e:
        logger.error(f"Error fetching weather data: {str(e)}")
        return f"Error fetching weather data: {str(e)}"


# ============================================
# RESOURCES
# ============================================


@mcp.resource("greeting://default")
def default_greeting() -> str:
    """A default greeting message."""
    logger.info("Resource 'greeting://default' requested")
    return "Hello! Welcome to the MCP Demo Server!"


# ============================================
# PROMPTS
# ============================================


@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Generate a greeting with different styles.

    Args:
        name: The person's name to greet.
        style: The style of greeting - 'friendly', 'formal', or 'casual'.
    """
    logger.info(f"Prompt 'greet_user' requested with name={name}, style={style}")

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
    # Always run over streamable-http on http://<host>:<port>/mcp
    # (host/port come from FASTMCP_HOST / FASTMCP_PORT, default 127.0.0.1:8000).
    transport = "streamable-http"
    endpoint = f"http://{mcp.settings.host}:{mcp.settings.port}/mcp"

    logger.info("=" * 60)
    logger.info("MCP Server is starting...")
    logger.info("Server Name: Demo Weather & Math Server")
    logger.info(f"Transport: {transport} ({endpoint})")
    logger.info("Registered Tools: add, subtract, get_weather")
    logger.info("Registered Resources: greeting://default")
    logger.info("Registered Prompts: greet_user")
    logger.info("=" * 60)
    logger.info("Server is now running and waiting for connections...")

    mcp.run(transport=transport)
