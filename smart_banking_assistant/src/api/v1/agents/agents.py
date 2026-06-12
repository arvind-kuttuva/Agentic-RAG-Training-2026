import os
from typing import Literal
import cohere
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from pydantic import BaseModel
import json

from src.api.v1.prompts.system_prompt import get_system_prompt
from src.api.v1.schema.query_schema import AIResponse
from src.api.v1.tools.tools import RAGState, _get_llm, fts_search, hybrid_search, nl2sql_query, vector_search
from src.api.v1.core.guardrails import guard_input, guard_output



load_dotenv()


# ── Node 0: Router ────────────────────────────────────────────────────────────
# Uses the OpenAI LLM (structured output) to classify the user's query.
#
# "productdb" → query is about credit cards, loans, fixed deposits, accounts, transactions
#             → routes to nl2sql_node (PostgreSQL / sba_rag_db_rdbms)
# "document" → query is about policies, procedures, text documents
#             → routes to the RAG pipeline (vector_search → rerank → generate_answer)


class _RouteDecision(BaseModel):
#    route: Literal["productdb", "fts", "document", "hybrid", "general_conversation"]
   route: Literal["productdb", "document", "hybrid", "general_conversation"]
   reason: str




def router_node(state: RAGState) -> RAGState:
   llm = _get_llm()
   structured_llm = llm.with_structured_output(_RouteDecision)


   prompt = ChatPromptTemplate.from_messages([
       (
           "system",
           """You are a strict query router for an agentic RAG system.

            Classify the user's query into EXACTLY one of four routes:

            "productdb"
                — Use ONLY when the query requires retrieving structured, user-specific, or transactional data from a database.
                — Examples:
                    - "show my account balance"
                    - "list my transactions"
                    - "my loan EMI details"
                    - "credit card outstanding"
                    - "mobile number linked to account"
                    - "account details for customer 12345"

                — IMPORTANT:
                Do NOT choose this for general questions about banking products.


        #    "fts" -     use when query contains exact identifiers like:
 	    #                 - RBI
 	    #                 - LTA, CTC, ESI
 	    #                 - numeric IDs like 123456                       


           "document" — the query asks about policies, procedures, guidelines,
                       regulations, or any topic that requires reading text documents.


           "hybrid" - the query has a combination of any of the above

           "general_conversation"
                — Use ONLY for polite niceties and conversational phrases:
                    - greetings: "hello", "hi"
                    - small talk: "how are you"
                    - gratitude: "thank you"
                    - identity: "who are you"

                — IMPORTANT:
                Do NOT select this for:
                    - general knowledge questions (e.g., weather, geography, science)
                    - queries unrelated to banking

                — If the query is unrelated to banking AND not a simple nicety, do NOT route to general_conversation.
                Instead, treat it as out-of-scope.

 
           Reply with the route and a one-sentence reason."""
       ),
       ("human", "Query: {query}")
   ])


   chain = prompt | structured_llm
   decision = chain.invoke({"query": state["query"]})
   print(f"[router_node] Route → '{decision.route}' | Reason: {decision.reason}")
   return {
       **state,
       "route": decision.route
   }

def general_conversation_node(state: RAGState) -> RAGState:
	llm = _get_llm()
	structured_llm = llm.with_structured_output(AIResponse)

	prompt = ChatPromptTemplate.from_messages([
    	(
        	"system",
        	"You are a helpful conversational banking assistant."
    	),
    	("human", "Question: {query}")
	])

	chain = prompt | structured_llm
	result = chain.invoke({"query": state["query"]})

	return {**state, "response": result.model_dump()}


# def fts_search_node(state: RAGState) -> RAGState:
#     docs = fts_search(state["query"],10)
#     return {**state, "fts_docs": docs}


def vector_search_node(state: RAGState) -> RAGState:
    docs = vector_search(state["query"], 10)
    return {**state, "vector_docs": docs}


def hybrid_search_node(state: RAGState) -> RAGState:
    docs = hybrid_search(state["query"], 10)
    return {**state, "hybrid_docs": docs}

def nl2sql_node(state: RAGState) -> RAGState:
    result = nl2sql_query(state["query"])
    return {
    	**state,
    	"generated_sql": result["generated_sql"],
    	"sql_result": result["sql_result"],
    	"response": result["response"]
	}


# ── Node 2: Rerank ──────────────────────────────────────────────────────────────
# Uses Cohere's cross-encoder reranker.
# Unlike bi-encoders (which embed query and doc separately),
# a cross-encoder sees query + doc TOGETHER → more accurate relevance scoring.


def rerank_node(state: RAGState) -> RAGState:
    co = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    vector_docs = state.get("vector_docs",[])
    # fts_docs = state.get("fts_docs",[])
    hybrid_docs = state.get("hybrid_docs",[])

    # all_docs = vector_docs + fts_docs + hybrid_docs
    all_docs = vector_docs + hybrid_docs

    if not all_docs:
        print("[rerank_node] No documents to rerank")
        return {**state, "reranked_docs": []}
    
    documents = [doc["content"] for doc in all_docs]
    
    rerank_response = co.rerank(
       model="rerank-english-v3.0",
       query=state["query"],
       documents=documents,
       top_n=min(5,len(documents))
    )


    # Map Cohere result indices back to LangChain Document objects
    reranked_docs = [all_docs[r.index] for r in rerank_response.results]


    print(f"[rerank_node] Top {len(reranked_docs)} chunks after reranking:")
    for i, r in enumerate(rerank_response.results):
        print(f"  Rank {i+1} | Cohere score: {r.relevance_score:.4f} | original index: {r.index}")


    return {**state, "reranked_docs": reranked_docs}




# ── Node 3: Generate Answer ─────────────────────────────────────────────────
# Formats the top 5 reranked chunks as context and calls the OpenAI LLM.
# Uses structured output to enforce the AIResponse schema.


def generate_answer_node(state: RAGState) -> RAGState:
    llm = _get_llm()
    structured_llm = llm.with_structured_output(AIResponse)


#    context = "\n\n".join([
#        f"[Source: {doc.metadata.get('source', 'unknown')} | Page: {doc.metadata.get('page', -1) + 1 if doc.metadata.get('page') is not None else '?'}]\n{doc.page_content}"
#        for doc in state["reranked_docs"]
#    ])

    context = "\n\n".join([
	f"[Source: {doc.get('metadata', {}).get('source', 'unknown')} | "
	f"Page: {doc.get('metadata', {}).get('page', -1) + 1 if doc.get('metadata', {}).get('page') is not None else '?'}]\n"
	f"{doc.get('content', '')}"
	for doc in state["reranked_docs"]
    ])

    sql_answer = ""
    sql_query = state.get("generated_sql")
    if isinstance(state.get("response"), dict):
        sql_answer = state.get("response", {}).get("answer","")

    prompt = ChatPromptTemplate.from_messages([
       (
           "system", get_system_prompt()          
       ),
       ("human",
        "Context:\n{context}\n\n"
        "SQL Answer:\n{sql_answer}\n\n"
        "Question: {query}")
   ])


    chain = prompt | structured_llm
    result = chain.invoke({"context": context, "sql_answer": sql_answer, "query": state["query"]})

    output = result.model_dump()

    print(f"[generate_answer_node] Answer generated.")
    if sql_query:
        output["answer"] += f"\n\nSQL Query used:\n {sql_query}"
    return {**state, "response": output}


# def route_logic(state):
#     route = state["route"]

#     if route == "hybrid":
#         return ["rag_retriever", "sql_generator"]
    
#     return [route]



# ── Build the LangGraph ────────────────────────────────────────────────────────
def build_rag_graph():
   graph = StateGraph(RAGState)


   graph.add_node("general_conversation",general_conversation_node)
   graph.add_node("query_classifier", router_node)
   graph.add_node("sql_generator", nl2sql_node)
   graph.add_node("vector_search", vector_search_node)
   graph.add_node("reranker", rerank_node)
   graph.add_node("response_generator", generate_answer_node)
   graph.add_node("rag_retriever",hybrid_search_node)
#    graph.add_node("fts_search", fts_search_node)


   graph.set_entry_point("query_classifier")


   # Conditional routing: "productdb" → nl2sql, "document" → vector_search
   graph.add_conditional_edges(
       "query_classifier",
       lambda state: state["route"],
        # route_logic,
       {
           "productdb": "sql_generator",
           "document": "vector_search",
           "hybrid": "rag_retriever",
        #    "fts": "fts_search",
           "general_conversation": "general_conversation"
       }
   )


   graph.add_edge("sql_generator", END)
   graph.add_edge("general_conversation", END)

   graph.add_edge("rag_retriever","reranker") 
#    graph.add_edge("fts_search","reranker")
   graph.add_edge("vector_search", "reranker")
   graph.add_edge("reranker", "response_generator")
   graph.add_edge("response_generator", END)


   compiled_agent = graph.compile()
   graph_image = compiled_agent.get_graph().draw_mermaid_png()
   with open("references/sba_workflow.png", "wb") as f:
       f.write(graph_image)


   return compiled_agent






# Compile once at module load — reused across all requests
rag_graph = build_rag_graph()






# ── Public entrypoint (called by query_service.py) ─────────────────────────
def run_search_agent(query: str) -> dict:
   initial_state: RAGState = {
       "query": query,
    #    "fts_docs": [],
       "vector_docs": [],
       "hybrid_docs": [],
       "retrieved_docs": [],
       "reranked_docs": [],
       "response": {},
       "route": "",
       "generated_sql": "",
       "sql_result": "",
   }
   final_state = rag_graph.invoke(initial_state)
   #return final_state["response"]["answer"]
   return final_state["response"]


async def run_search_agent_stream(query: str):
   initial_state: RAGState = {
       "query": query,
    #    "fts_docs": [],
       "vector_docs": [],
       "hybrid_docs": [],
       "retrieved_docs": [],
       "reranked_docs": [],
       "response": {},
       "route": "",
       "generated_sql": "",
       "sql_result": "",
   }
   final_state = rag_graph.invoke(initial_state)
   async for event in rag_graph.astream_events(initial_state, version="v1"):
        kind = event["event"]

        # If its a token generated by chat model
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                # Format as an SSE data stream payload
                yield f"data: {json.dumps({'token': content})}\n\n"

   yield "data: [DONE]\n\n"
