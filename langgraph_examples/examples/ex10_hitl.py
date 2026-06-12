# this example demonstrates a simple agent workflow
# with human-in-the-loop review and revision.
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env file


llm = ChatOpenAI(model="gpt-5.4")


# 1. State
class AgentState(TypedDict):
   query: str
   draft_answer: str
   approved: bool
   final_answer: str

def draft_node(state: AgentState) -> AgentState:
    """Create a draft answer"""
    print("Drafting answer")
    response = llm.invoke(f"""Anser the following question concisely:
                            {state['query']}""")
    return {
        **state,
        "draft_answer": response.content
    }


def human_review_node(state: AgentState) -> AgentState:
    """
    Simulate human approval
    (In real apps: UI/API/interrupt)   
    """

    print(f"\n Review this answer:\n{state['draft_answer']}")
    #simulate human input
    user_input = input("Approve? (yes/no): ").strip().lower()
    approved = user_input == "yes"
    return {
        **state,
        "approved": approved
    }


def finalize_node(state: AgentState) -> AgentState:
    """Finalize approved answer"""
    print("Approved, Sending answer")

    return {
        **state,
        "final_answer": state["draft_answer"]
    }


def revise_node(state: AgentState) -> AgentState:
    """Revise answer if rejected"""
    print("Revising answer....")

    return {
        **state,
        "draft_answer": state["draft_answer"] + " (revised)"
    }


#3. Router
def route(state: AgentState) -> str:
    return "finalize" if state["approved"] else "revise"


#4. Build graph
workflow = StateGraph(AgentState)    

workflow.add_node("draft", draft_node)
workflow.add_node("review", human_review_node)
workflow.add_node("finalize", finalize_node)
workflow.add_node("revise", revise_node)

workflow.add_edge(START, "draft")
workflow.add_edge("draft", "review")

workflow.add_conditional_edges(
    "review",
    route,
    {
        "finalize": "finalize",
        "revise": "revise"
    }
)

workflow.add_edge("revise", "review")
workflow.add_edge("finalize", END)

#5. Compile
app = workflow.compile()
# Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex10_hitl.png", "wb") as f:
   f.write(graph_image)


#6. Run
result = app.invoke({
    "query": "Explain LangGraph simply",
    "draft_answer": "",
    "approved": False,
    "final_answer": ""
})