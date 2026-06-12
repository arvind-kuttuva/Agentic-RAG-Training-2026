from typing import TypedDict
from langgraph.graph import StateGraph, START, END

#1. State
class NumberState(TypedDict):
    number: int
    is_valid: bool
    attempts: int


#2. Nodes
def validate_number(state: NumberState) -> NumberState:
    """check if number is valid (positive number)"""
    num = state["number"]
    print(f"checking:{num}")

    is_valid = num > 0

    return {
        **state,
        "is_valid": is_valid,
        "attempts": state["attempts"] + 1
    }
    

def retry_node(state: NumberState) -> NumberState:
    """Simulate retry (fixing the input)"""
    print("Invalid number. Retrying...")

    #Simulate user correcting input
    new_number = state["number"] + 5

    return{
        **state,
        "number": new_number
    }

def success_node(state: NumberState) -> NumberState:
    """Final Success"""
    print("valid number found")

    return state


#3 . Router (loop decision)
def route(state: NumberState) -> str:
    if state["is_valid"]:
        return "success"
    return "retry"

#4. Build Graph
workflow = StateGraph(NumberState)

workflow.add_node("success", success_node)
workflow.add_node("retry", retry_node)
workflow.add_node("validate", validate_number)

workflow.add_edge(START, "validate")

workflow.add_conditional_edges(
    "validate",
    route,
    {
        "success": "success",
        "retry": "retry"
    }
)

# This is the most important part (loop)
workflow.add_edge("retry", "validate")
workflow.add_edge("success", END)

#5. Compile
app = workflow.compile()


#Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex4_loops.png", "wb") as f:
    f.write(graph_image)

workflow_result = app.invoke({"number": -10, "is_valid": False, "attempts": 0}) # we are not sending result here

print("\n Final state: ", workflow_result)
# print("*" * 50)

# for key, value in workflow_result.items():
#     print(f"{key}: {value}")