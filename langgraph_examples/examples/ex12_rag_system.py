from typing import TypedDict, List
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(model="gpt-5.4", temperature=0)

#users preference
LONG_TERM_MEMORY = ["user prefers simple explanations"]

#Original content from vector db
DOCUMENTS= {
    "solar system": "The solar system is a gravitationally bound system of stars",
    "rag": "RAG combines retrieval with generation using external knowledge"
}

#1. State
class AgentState(TypedDict):
    query: str
    memory: List[str]
    context: str
    answer: str
    is_good: bool
    attempts: int

#2. Nodes
def retrieve_memory(state: AgentState) -> AgentState:
    print("Retrieving Memory")    
    return {
        **state,
        "memory": LONG_TERM_MEMORY
    }



def retrieve_docs(state: AgentState) -> AgentState:
    print("Retrieving documents")

    #in a real app, you'd do something like:
    # vectorstore.similarity_search(query)
    query = state["query"].lower()
    context = ""

    for key, value in DOCUMENTS.items():
        if key in query:
            context += value + "\n"

    if not context:
        context = "No relevant documents found."

    return {
        **state,
        "context": context
    }


def generate_node(state: AgentState) -> AgentState:
    print("Generating answer...")

    memory_text = "\n".join(state["memory"])

    prompt = f"""
        User preferences:
        {memory_text}

        Context:
        {state['context']}

        Question:
        {state['query']}

        Answer clearly and exactly without exaggerating.
    """

    answer = llm.invoke(prompt).content

    return {
        **state,
        "answer": answer,
        "attempts": state["attempts"] + 1
    }


def evaluate_node(state: AgentState) -> AgentState:
    print(" Evaluating answer")

    prompt = f"""
    Question: {state['query']}
    Context: {state['context']}
    Answer: {state['answer']}

    Is the answer correct and complete based on the context?

    Respond with only: yes or no
    """

    result = llm.invoke(prompt).content.strip().lower()

    return {
        **state,
        "is_good": result == "yes"
    }


#3. Router

def route(state: AgentState) -> str:
    if state["is_good"] or state["attempts"] >= 3:
        return "end"
    return "retry"


#4. Build graph
workflow = StateGraph(AgentState)

workflow.add_node("memory", retrieve_memory)
workflow.add_node("retrieve", retrieve_docs)
workflow.add_node("generate", generate_node)
workflow.add_node("evaluate", evaluate_node)

workflow.add_edge(START, "memory")
workflow.add_edge("memory", "retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "evaluate")

workflow.add_conditional_edges(
    "evaluate",
    route,
    {
        "retry": "generate",
        "end": END
    }
)


#5. Compile
app = workflow.compile()
# Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex8_tool_node.png", "wb") as f:
   f.write(graph_image)


#6. Run
result = app.invoke({
    "query": "What is solar system?",
    "memory": [],
    "context": "",
    "answer": "",
    "is_good": False,
    "attempts": 0
})

print("\n Final answer", result["answer"])
print("Attempts:", result["attempts"])