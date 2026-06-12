from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-5.4")

#1. State
class AgentState(TypedDict):
    query: str
    decision: str
    response: str


#2. Nodes
def prompt_review_node(state: AgentState) -> AgentState:
    "LLM decides if query is CLEAR or UNCLEAR"

    query = state["query"]

    prompt = f"""
    Classify the user query as:
    - clear
    - unclear
    Prompt:
    Query: {query}

    Respond only with one word: clear or unclear
    """

    decision = llm.invoke(prompt).content.strip().lower()
    print(f" LLM decision: {decision}")

    return{
        **state,
        "decision": decision
    }

def answer_node(state: AgentState) -> AgentState:
    # connect to the llm go get answer
    prompt = f"""Answer the following question clearly and concisely:
    {state['query']}
    """
    answer = llm.invoke(prompt)
    return {
        **state,
        "response": f"Answering clearly : {state['query']}\n{answer.content}"
    }

def clarify_node(state: AgentState) -> AgentState:
    return {
        **state,
        "response": f"Can you clarify your question: '{state['query']}'?"
    }

#3. Router (based on LLM output)
def route(state: AgentState) -> str:
    return state["decision"]


#4. Build graph
workflow = StateGraph(AgentState)

workflow.add_node("prompt_review", prompt_review_node)
workflow.add_node("answer", answer_node)
workflow.add_node("clarify", clarify_node)

workflow.add_edge(START, "prompt_review")

workflow.add_conditional_edges(
    "prompt_review",
    route,
    {
        "clear": "answer",
        "unclear": "clarify"
    }
)

workflow.add_edge("answer", END)
workflow.add_edge("clarify", END)

#5. Compile
app = workflow.compile()


#Generate and save the graph visualization
graph_image = app.get_graph().draw_mermaid_png()
with open("examples/ex4_loops.png", "wb") as f:
    f.write(graph_image)

#6. Run
result = app.invoke({
    # "query": "Explain quantum computing in simple terms",
    "query": "random gibberish that doesnt make sense",
    "decision": "",
    "response": ""
})    

print("\nFinal:", result["response"])