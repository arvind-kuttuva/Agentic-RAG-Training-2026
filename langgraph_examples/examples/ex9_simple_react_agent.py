# this example demonstrates a simple agent workflow with a loop for
# iterative thinking and acting until a final answer is reached.
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables.graph import MermaidDrawMethod
import os
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file


llm = ChatOpenAI(model="gpt-5.4")


# 1. State
class AgentState(TypedDict):
   query: str
   thought: str
   action: str
   observation: str
   final_answer: str




# 2. Tools


def search_tool(query: str) -> str:
   return f"Search result for '{query}': LangGraph is a framework for building agents."


def calculator_tool(expression: str) -> str:
   try:
       return str(eval(expression))
   except:
       return "error"


# 3. Nodes
def think_node(state: AgentState) -> AgentState:
   """
   LLM decides next action
   """
   prompt = f"""
   You are an agent. Decide next step:


   Query: {state['query']}
   Previous observation: {state['observation']}


   Choose one:
   - search
   - calculate
   - finish


   Respond with one word.
   """


   action = llm.invoke(prompt).content.strip().lower()


   print("=============")
   print(f"🧠 Thought → {action}")


   return {
       **state,
       "action": action
   }




def act_node(state: AgentState) -> AgentState:
   """
   Executes tool based on action
   """
   action = state["action"]


   if action == "search":
       result = search_tool(state["query"])
   elif action == "calculate":
       result = calculator_tool(state["query"])
   else:
       result = "No action"


   print(f"⚙️ Action → {action}")
   print(f"👀 Observation → {result}")


   return {
       **state,
       "observation": result
   }




def answer_node(state: AgentState) -> AgentState:
   """
   Final answer
   """
   response = llm.invoke(
       f"Answer the query using this info: {state['observation']}"
   )


   return {
       **state,
       "final_answer": response
   }




# 4. Router (loop control)


def route(state: AgentState) -> str:
   if state["action"] == "finish":
       return "answer"
   return "act"




# 5. Build graph


workflow = StateGraph(AgentState)


workflow.add_node("think", think_node)
workflow.add_node("act", act_node)
workflow.add_node("answer", answer_node)


workflow.add_edge(START, "think")


workflow.add_conditional_edges(
   "think",
   route,
   {
       "act": "act",
       "answer": "answer"
   }
)


# 🔁 Loop
workflow.add_edge("act", "think")


workflow.add_edge("answer", END)


# 6. Compile
app = workflow.compile()
# Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex8_simple_react_agent.png", "wb") as f:
   f.write(graph_image)


# 7. Run
result = app.invoke({
   "query": "What is LangGraph?",
   "thought": "",
   "action": "",
   "observation": "",
   "final_answer": ""
})


print("\nFinal Answer:", result["final_answer"].content)