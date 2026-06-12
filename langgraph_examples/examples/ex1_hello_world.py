from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    print("Mock LLM received messages: ", state)
    return {"messages": [{"role": "ai", "content": "hello world"}]}

#Define the graph
# Our graph will deal with msgs, so use MessagesState as the state type
graph = StateGraph(MessagesState)

graph.add_node("mock_llm", mock_llm) #box representing language model
graph.add_edge(START, "mock_llm") #arrow from start to mock_llm model
graph.add_edge("mock_llm", END) #arrow from the mock_llm node to the end
graph = graph.compile()

#Generate and save the graph visualization
graph_image = graph.get_graph().draw_mermaid_png()
with open("examples/ex1_hello_world.png", "wb") as f:
    f.write(graph_image)


result = graph.invoke({"messages": [
    {
        "role": "user", "content": "hi"
    }
]})
print("*" *50)
print(result)