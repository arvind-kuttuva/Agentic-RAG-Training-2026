from typing import TypedDict, Annotated
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


load_dotenv()

# LLM
llm = ChatOpenAI(
    model="gpt-5"
)

# State
class ChatState(TypedDict):
    messages: Annotated[list, add_messages]


# Node
def chatbot_node(state: ChatState):
    response = llm.invoke(state["messages"])

    return {
        "messages": [response]
    }


# Build Graph
graph_builder = StateGraph(ChatState)

graph_builder.add_node("chatbot", chatbot_node)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)

checkpointer = MemorySaver()
app = graph_builder.compile(checkpointer=checkpointer)


# Terminal Chat Loop
def main():
    print("=" * 50)
    print("LangGraph Terminal Chatbot")
    print("Type 'exit' to quit")
    print("=" * 50)

    state = {"messages": []}

    while True:
        user_input = input("\nYou: ")

        if user_input.lower() in ["exit", "quit"]:
            break

        state["messages"].append(
            HumanMessage(content=user_input)
        )

        state = app.invoke(state)

        print(
            f"\nAssistant: {state['messages'][-1].content}"
        )

if __name__ == "__main__":
    main()