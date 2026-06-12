from typing import TypedDict
from langgraph.graph import StateGraph, MessagesState, START, END

#1. State
class NumberState(TypedDict):
    number: int
    result: str

#2. Nodes
def check_number(state: NumberState) -> NumberState:
    """Decide if number is even or odd"""
    print(f"Checking number: {state['number']}")
    return state


def even_node(state: NumberState) -> NumberState:
    """Handles even numbers"""
    return {
        **state, #unpacking dict variables- feature in python
        "result": f"{state['number']} is even"
    }


def odd_node(state: NumberState) -> NumberState:
    """Handles odd numbers"""
    return {
        **state, #unpacking dict variables- feature in python
        "result": f"{state['number']} is odd"
    }


#3. Router (this is if/else)    
def route(state: NumberState) -> str:
    if state["number"] % 2 == 0:
        return "even"
    return "odd"


#4. Build graph
workflow = StateGraph(NumberState)

workflow.add_node("check", check_number)
workflow.add_node("even", even_node)
workflow.add_node("odd", odd_node)

workflow.add_edge(START, "check")

#making check node as router node
workflow.add_conditional_edges(
    "check", # conditional node
    route, # routing function
    {
        "even": "even",
        "odd": "odd"
    } #mapping of route outputs to node names
)

workflow.add_edge("even", END)
workflow.add_edge("odd", END)

#5. Compile
app = workflow.compile()

#Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex3_router.png", "wb") as f:
    f.write(graph_image)

workflow_result = app.invoke({"number": 6}) # we are not sending result here
print(workflow_result)