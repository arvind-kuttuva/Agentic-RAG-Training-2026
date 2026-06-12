from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.runnables.graph import MermaidDrawMethod
import requests
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file


llm = ChatOpenAI(model="gpt-5.4")




# 1. State
class AgentState(TypedDict):
   query: str
   tool: str
   result: str




# 2. Tools
def calculator_tool(expression: str) -> str:
   """Very simple calculator"""
   try:
       return str(eval(expression))
   except:
       return "Error in calculation"




def weather_tool(location: str) -> str:
   """Fetch current weather for a location using Open-Meteo (no API key required)"""
   # Step 1: Geocode the location
   geo_url = "https://geocoding-api.open-meteo.com/v1/search"
   geo_resp = requests.get(geo_url, params={"name": location, "count": 1}, timeout=10)
   geo_data = geo_resp.json()


   if not geo_data.get("results"):
       return f"Could not find location: {location}"


   place = geo_data["results"][0]
   lat, lon = place["latitude"], place["longitude"]
   city_name = place.get("name", location)
   country = place.get("country", "")


   # Step 2: Fetch current weather
   weather_url = "https://api.open-meteo.com/v1/forecast"
   weather_resp = requests.get(
       weather_url,
       params={
           "latitude": lat,
           "longitude": lon,
           "current_weather": True,
           "wind_speed_unit": "kmh",
       },
       timeout=10,
   )
   weather_data = weather_resp.json()
   cw = weather_data.get("current_weather", {})


   temp = cw.get("temperature", "N/A")
   wind = cw.get("windspeed", "N/A")
   # WMO weather code rough mapping
   wmo_code = cw.get("weathercode", -1)
   condition = (
       "Clear" if wmo_code == 0
       else "Mainly clear / partly cloudy" if wmo_code in (1, 2, 3)
       else "Foggy" if wmo_code in range(45, 50)
       else "Drizzle" if wmo_code in range(51, 58)
       else "Rain" if wmo_code in range(61, 68)
       else "Snow" if wmo_code in range(71, 78)
       else "Thunderstorm" if wmo_code in range(95, 100)
       else f"Weather code {wmo_code}"
   )


   return (
       f"Weather in {city_name}, {country}: {condition}, "
       f"Temperature: {temp}°C, Wind speed: {wind} km/h"
   )



# 3. Nodes
def decide_tool_node(state: AgentState) -> AgentState:
   """
   LLM decides which tool to use:
   - incorrectentry
   - calculator
   - weather
   - answer
   """
   query = state["query"]


   prompt = f"""
   check whether the prompt is valid  and then Decide the best tool:
   - incorrectentry (if the query is invalid)
   - calculator (for math expressions)   
   - weather (for weather queries about a city or location)   
   - answer (for all other general questions)
   


   Query: {query}


   Respond with only one word.
   """


   response = llm.invoke(prompt)
   content = response.content
   if isinstance(content, list):
       tool = "".join(item.get("text", "") for item in content if item.get("type") == "text").strip().lower()
   else:
       tool = content.strip().lower()


   print(f"🧠 Tool selected: {tool}")


   return {
       **state,
       "tool": tool
   }




def calculator_node(state: AgentState) -> AgentState:
   print("🧮 Using calculator")


   result = calculator_tool(state["query"])


   return {
       **state,
       "result": f"Calculation result: {result}"
   }




def weather_node(state: AgentState) -> AgentState:
   print("🌤️  Fetching weather")


   # Ask LLM to extract just the location name from the query
   extract_prompt = f"Extract only the city or location name from this query (respond with just the name): {state['query']}"
   location = llm.invoke(extract_prompt).content.strip()


   result = weather_tool(location)


   return {
       **state,
       "result": result
   }




def answer_node(state: AgentState) -> AgentState:
   print("💬 Generating answer")


   response = llm.invoke(state["query"]).content


   return {
       **state,
       "result": response
   }

def incorrectentry_node(state:AgentState) -> AgentState:
    print("inside incorrect entry node")
    return {
       **state,
       "result": "Pl provide a valid query"
   }


# 4. Router


def route(state: AgentState) -> str:
   return state["tool"]




# 5. Build graph


workflow = StateGraph(AgentState)


workflow.add_node("decide_tool", decide_tool_node)
workflow.add_node("calculator", calculator_node)
workflow.add_node("weather", weather_node)
workflow.add_node("answer", answer_node)
workflow.add_node("incorrectentry", incorrectentry_node)


workflow.add_edge(START, "decide_tool")


workflow.add_conditional_edges(
   "decide_tool",
   route,
   {
       "calculator": "calculator",
       "weather": "weather",
       "answer": "answer",
       "incorrectentry": "incorrectentry"
   }
)


workflow.add_edge("calculator", END)
workflow.add_edge("weather", END)
workflow.add_edge("answer", END)
workflow.add_edge("incorrectentry", END)



# 6. Compile
app = workflow.compile()


# Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex7_tool_workflow.png", "wb") as f:
   f.write(graph_image)






# 7. Run


# print("\n--- Example 1 (Math) ---")
# result1 = app.invoke({
#    "query": "25 * 4 + 10",
#    "tool": "",
#    "result": ""
# })
# print("Final:", result1["result"])




print("\n--- Example 2 (Weather) ---")
result2 = app.invoke({
   "query": "What is the current weather in Hogwartz?",
   "tool": "",
   "result": ""
})
print("Final:", result2["result"])




# print("\n--- Example 3 (General) ---")
# result3 = app.invoke({
#     "query": "What is LangGraph?",
#     "tool": "",
#     "result": ""
# })
# print("Final:", result3["result"])
