from typing import TypedDict
from langgraph.graph import StateGraph, START, END

#defining custom state
class SimpleState(TypedDict):
    user_name: str
    message: str


def greet_node(state: SimpleState):
    print("\n=============1.GREET NODE===========")
    print("Received State:", state) # current state printed to console for debugging

    greeting_message = f"Hello {state['user_name']} Welcome to langgraph example"
    return {"message": greeting_message} #updated state with greeting message

def status_node(state: SimpleState):
    print("\n=============2. STATUS NODE===========")
    print("Received State:", state) # current state printed to console for debugging

    status_message = f"Status: Workflow Executed."
    return {"message": status_message} #updated message

#2 defining the graph
workflow = StateGraph(SimpleState)

workflow.add_node("greet", greet_node)
workflow.add_node("status", status_node)

workflow.add_edge(START, "greet")
workflow.add_edge("greet", "status")
workflow.add_edge("status", END)

workflow = workflow.compile()

#Generate and save the graph visualization
graph_image = workflow.get_graph().draw_mermaid_png()
with open("examples/ex2_greet.png", "wb") as f:
    f.write(graph_image)

workflow_result = workflow.invoke({"user_name": "Alice"})
print("*" * 50)

for key, value in workflow_result.items():
    print(f"{key}: {value}")
