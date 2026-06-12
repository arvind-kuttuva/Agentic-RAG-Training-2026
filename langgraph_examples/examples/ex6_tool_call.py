# this example demonstrates how to have the LLM dynamically
# call multiple tools in a single response,
# and how to structure the graph and state for that use case.
# The agent_node will keep invoking the LLM until there are
# no more tool calls in the response, allowing for complex
# interactions where the LLM can decide to call multiple tools
# in sequence.
from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import requests
from dotenv import load_dotenv


load_dotenv()


llm = ChatOpenAI(model="gpt-5.4")


# =========================
# 1. Define Tools (@tool)
# =========================


@tool
def calculator_tool(expression: str) -> str:
   """Evaluate a math expression
       Args: expression (str): math expression to evaluate
       Returns: str: result of the calculation
   """
   try:
       return str(eval(expression))
   except:
       return "Error in calculation"




@tool
def weather_tool(location: str) -> str:
   """Get current weather for a city
       Args: location (str): city name
       Returns: str: weather info
   """
   try:
       geo_url = "https://geocoding-api.open-meteo.com/v1/search"
       geo_resp = requests.get(geo_url, params={"name": location, "count": 1}, timeout=10)
       geo_data = geo_resp.json()


       if not geo_data.get("results"):
           return f"Could not find location: {location}"


       place = geo_data["results"][0]
       lat, lon = place["latitude"], place["longitude"]
       city_name = place.get("name", location)
       country = place.get("country", "")


       weather_url = "https://api.open-meteo.com/v1/forecast"
       weather_resp = requests.get(
           weather_url,
           params={
               "latitude": lat,
               "longitude": lon,
               "current_weather": True,
           },
           timeout=10,
       )


       data = weather_resp.json()
       current_weather = data.get("current_weather", {})


       return f"Weather in {city_name}, {country}: {current_weather}"
   except Exception as e:
       return f"Error fetching weather for {location}: {e}"




tools = [calculator_tool, weather_tool]


# Bind tools to LLM
llm_with_tools = llm.bind_tools(tools)




# =========================
# 2. State
# =========================


class AgentState(TypedDict):
   query: str
   messages: List
   result: str




# =========================
# 3. Node (LLM decides + calls tool)
# =========================


def agent_node(state: AgentState) -> AgentState:
   print("🤖 Agent thinking...")


   messages = list(state["messages"])
   tool_map = {t.name: t for t in tools}


   # dynamically call tools until LLM has no more tool calls in its response
   while True:
       response = llm_with_tools.invoke(messages) # human msg will go
       # print(f"💬 Agent response: {response}")
       messages.append(response) # ai response will get added to the messages


       print("**************")
       print(f"💬 Response Tool Calls: {response.tool_calls}")
       print("**************")
       if not response.tool_calls:
           # No more tools — final answer
           break


       # Execute all tool calls in this response
       for tool_call in response.tool_calls:
           tool_name = tool_call["name"]
           tool_args = tool_call["args"]
           tool_call_id = tool_call["id"]


           print(f"🛠️ Tool selected: {tool_name}")
           print(f"📦 Args: {tool_args}")


           tool_fn = tool_map[tool_name]
           tool_result = tool_fn.invoke(tool_args)


           print(f"📊 Tool result: {tool_result}")


           messages.append({
               "role": "tool",
               "content": str(tool_result),
               "name": tool_name,
               "tool_call_id": tool_call_id
           })


   return {
       **state,
       "messages": messages,
       "result": response.content
   }




# =========================
# 4. Build Graph
# =========================


workflow = StateGraph(AgentState)


workflow.add_node("agent", agent_node)


workflow.add_edge(START, "agent")
workflow.add_edge("agent", END)


app = workflow.compile()


# Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex6_tool_call.png", "wb") as f:
   f.write(graph_image)


# =========================
# 5. Run
# =========================


# print("\n--- Example 1 (Math) ---")
# result1 = app.invoke({
#     # "query": "25 * 4 + 10",
#     "messages": [{"role": "user", "content": "25 * 4 + 10"}],
#     "result": ""
# })
# print("Final:", result1["result"])




# print("\n--- Example 2 (Weather) ---")
# result2 = app.invoke({
#    # "query": "What is the weather in Chennai and multiply that by 2",
#    "messages": [{"role": "user", "content": "What is the weather in Chennai and multiply that by 2?"}],
#    "result": ""
# })
# print("Final:", result2["result"])




# print("\n--- Example 3 (General) ---")
# result3 = app.invoke({
#     "query": "What is LangGraph?",
#     "messages": [{"role": "user", "content": "What is LangGraph?"}],
#     "result": ""
# })
# print("Final:", result3["result"])



