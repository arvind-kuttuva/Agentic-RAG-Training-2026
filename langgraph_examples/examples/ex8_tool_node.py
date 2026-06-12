from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import requests
from dotenv import load_dotenv

load_dotenv()

# =========================
# 1. LLM
# =========================
llm = ChatOpenAI(model="gpt-5.4")

# =========================
# 2. Tools
# =========================


@tool
def calculator_tool(expression: str) -> str:
   """Evaluate a math expression
       Args: expression (str): math expression to evaluate
       Returns: str: result of the calculation
   """
   print("calling calculator_tool")
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
   print("calling weather_tool")
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
# 3. State
# =========================

class AgentState(TypedDict):
    messages: Annotated[List, add_messages] #messages is the conversation memory. 
    #LangGraph automatically appends messages via add_messages

# =========================
# 4. Agent Node (LLM only)
# =========================    

def agent_node(state: AgentState):
    response = llm_with_tools.invoke(state["messages"])

    return {
        "messages": [response]
    }


# =========================
# 5. Conditional Routing
# =========================    
def should_continue(state: AgentState):
    last_message = state["messages"][-1]

    #llm wants tools, continue. Else end
    #langgraph does not decide tools. LLM does that via tool_calls
    if last_message.tool_calls:
        return "tools"

    return END

# =========================
# 6. Tool Node (prebuilt)
# =========================

#Initializing ToolNode with tools and configurations.
tool_node = ToolNode(tools) # this is the tool executor

# =========================
# 7. Build Graph
# =========================
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node) #thinking node - LLM reasoning
workflow.add_node("tools", tool_node) #Execution node - runs tools

workflow.add_edge(START, "agent") #Entrypoint

workflow.add_conditional_edges( #brain of the graph. conditional routing. Execute agent, execute should_continue which will return either tools or end 
    "agent",
    should_continue,
    ["tools", END]
)

workflow.add_edge("tools", "agent") # this creates the agent -> tools loop

app = workflow.compile()
# Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex8_tool_node.png", "wb") as f:
   f.write(graph_image)


# =========================
# 8. Run Example
# =========================   
print("\n--- Example 2 (Weather) ---")
result = app.invoke({
   # "query": "What is the weather in Chennai and multiply that by 2",
   "messages": [{"role": "user", "content": "What is the weather in Chennai and multiply that by 2?"}],
   "result": ""
})
print("Final:", result["messages"][-1].content)