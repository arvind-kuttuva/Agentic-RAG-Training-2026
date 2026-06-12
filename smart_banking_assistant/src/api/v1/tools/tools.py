import hashlib
import os
from dotenv import load_dotenv
from typing import TypedDict, List, Dict, Any
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from src.api.v1.schema.query_schema import AIResponse
from src.api.v1.core.db import get_vector_store
from src.api.v1.core.db import get_sql_database
from langchain_core.prompts import ChatPromptTemplate
import psycopg
from psycopg.rows import dict_row

load_dotenv()

# ── Helper: build the OpenAI LLM ──────────────────────────────────────────────


def _get_llm() -> ChatOpenAI:
   return ChatOpenAI(
       model=os.getenv("OPENAI_CHAT_MODEL"),
       api_key=os.getenv("OPENAI_API_KEY")
   )


# ── State ──────────────────────────────────────────────────────────────────────
# The state is the shared data that flows through the entire graph.
# Each node reads from state and returns updated state.


class RAGState(TypedDict):
    query: str
    # fts_docs: List[Dict[str, Any]]
    vector_docs: List[Dict[str, Any]]
    hybrid_docs: List[Dict[str, Any]]
    retrieved_docs: List[Dict[str, Any]]  # Output of Node 1 — wide retrieval (k=20)
    reranked_docs: List[Dict[str, Any]]  # Output of Node 2 — narrowed by reranker (top_n=10)
    response: dict  # final structured answer
    route: str  # "product" or "document" - set by router_node
    generated_sql: str  #
    sql_result: str


# ── Node NL2SQL: Translate query to SQL → Execute → Summarise ─────────────────
# Step 1  Build a prompt with the live DB schema (table/column names + 2 sample
#          rows per table) and ask the LLM to write a single SELECT statement.
# Step 2  SQLDatabase.run() executes the SQL as the read-only sba_rag_readonly user.
#          Even if the LLM hallucinated a DML statement, the DB role blocks it.
# Step 3  The LLM summarises the raw results as a structured AIResponse.


def nl2sql_query(query: str) -> dict:
   llm = _get_llm()
   db = get_sql_database()


   # ── Step 1: Generate SQL using the LLM + live schema ────────────────────
   schema_info = db.get_table_info()


   sql_prompt = ChatPromptTemplate.from_messages([
       (
           "system",
           """You are a PostgreSQL expert. Given the database schema below,
           write a single valid SELECT query that answers the user's question.


           Rules:
           - Return ONLY the raw SQL — no explanation, no markdown fences, no backticks.
           - Use only the tables and columns present in the schema.
           - Do NOT generate INSERT, UPDATE, DELETE, DROP, or any DML/DDL statements.
           - Always add a LIMIT clause (max 50 rows) unless the question asks for aggregates.
           - For product or text searches: NEVER search for the full multi-word phrase as one
           ILIKE pattern. Instead, split the search into individual meaningful keywords
           and OR them together across both name and description columns.
           Example — user asks "%ifsccode%":
               WHERE (name ILIKE '%NorthStar Gold%' OR txntype ILIKE '%purchase%')
               OR (name ILIKE '%fixed deposit rates%'  OR description ILIKE '%fixed deposit rates%')
               OR (name ILIKE '%loan interest rates%' OR description ILIKE '%loan interest rates%')
           Use your knowledge of synonyms (Fixed Deposits/FDs, housing loan/mortgage, etc.)
           to cast a wider net when the exact term may not match.


           Database schema:
           {schema}"""
       ),
       ("human", "Question: {question}")
   ])


   sql_chain = sql_prompt | llm
   raw_sql = sql_chain.invoke({
       "schema": schema_info,
       "question": query
   })
   # The LLM may return content as a list of parts or a plain string
   content = raw_sql.content
   if isinstance(content, list):
       content = "".join(
           p.get("text", "") if isinstance(p, dict) else str(p)
           for p in content
       )
   generated_sql = content.strip().strip("```").strip()
   if generated_sql.lower().startswith("sql"):
       generated_sql = generated_sql[3:].strip()
   print(f"[nl2sql_node] Generated SQL:\n{generated_sql}")


   # ── Step 2: Execute SQL ──────────────────────────────────────────────────
   try:
       sql_result: str = db.run(generated_sql)
   except Exception as exc:
       sql_result = f"SQL execution error: {exc}"
   print(f"[nl2sql_node] Raw result (truncated): {str(sql_result)[:200]}")


   # ── Step 3: Summarise into AIResponse ────────────────────────────────────
   structured_llm = llm.with_structured_output(AIResponse)
   answer_prompt = ChatPromptTemplate.from_messages([
       (
           "system",
           "You are a helpful data analyst. Answer the user's question using "
           "the SQL query results below. Be concise and format numbers/lists clearly. "
           "Set policy_citations to empty string, "
           "page_no to 'N/A', and document_name to 'sba_rag_db'."
       ),
       (
           "human",
           "Question: {query}\n\n"
           "SQL Used:\n{sql}\n\n"
           "Query Results:\n{result}"
       )
   ])


   chain = answer_prompt | structured_llm
   answer = chain.invoke({
       "query": query,
       "sql": generated_sql,
       "result": sql_result
   })
   print("[nl2sql_node] Answer generated.")
   response = answer.model_dump()
   response["policy_citations"] = "N/A"
   response["sql_query_executed"] = generated_sql
   print(f"response = {response}")
   return {       
       "generated_sql": generated_sql,
       "sql_result": str(sql_result),
       "response": response
   }


# ── Node: Vector Search ──────────────────────────────────────────────────────
# Uses a bi-encoder (OpenAI embeddings) to find semantically similar chunks.
# We retrieve k=10 to cast a wide net — the reranker will narrow this down to top 5.


def vector_search(query:str, k:int):
    retriever = get_vector_store()
    docs = retriever.similarity_search(query, k=k)
    print(f"[vector_search_node] Retrieved {len(docs)} chunks from PGVector")
    return [
        {"content": doc.page_content, "metadata": doc.metadata}
        for doc in docs
    ]


def clean_query(query: str):
    stopwords = {"explain", "what", "tell", "me", "about"}
    tokens = query.lower().replace(".", " ").split()
    return " ".join(t for t in tokens if t not in stopwords)


def build_or_tsquery(query: str) -> str:
    tokens = query.lower().replace(".", " ").split()
    return " | ".join(tokens)


#fts search
def fts_search(query: str, k: int):
    """full text search for abbreviations and queries that match the regular expression patterns"""
    print("inside fts_search")
        
    _PG_CONNECTION_VECTOR = os.getenv("PG_CONNECTION_STRING_VECTOR", "")
    _PG_DSN = _PG_CONNECTION_VECTOR.replace("postgresql+psycopg://", "postgresql://")
    sql = """
       SELECT
           e.content                                               AS content,
           e.metadata                                               AS metadata,
           ts_rank(
               to_tsvector('english', e.content),
               plainto_tsquery('english', %(query)s)
           )                                                     AS fts_rank
       FROM  multimodal_chunks  e
       JOIN  documents c ON c.id = e.document_id
       WHERE to_tsvector('english', e.content)
             @@ plainto_tsquery('english', %(query)s)
       ORDER BY fts_rank DESC
       LIMIT %(k)s;
    """
    with psycopg.connect(_PG_DSN, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"query": query,
                            "k": k})
        
            rows = cur.fetchall()
    
    return [
        {
            "content": row["content"],
            "metadata": row["metadata"],
            # "fts_rank": round(float(row["fts_rank"]), 4),
        }
        for row in rows
    ]


def hybrid_search(query: str, k: int):
    print(f"[hybrid_search] Query: {query}")

    # 1. Vector search
    vector_docs = vector_search(query, k=k)

    # 2. FTS search (clean + OR query)
    # fts_query = build_or_tsquery(clean_query(query))
    # fts_docs = fts_search(fts_query, k=k)
    # fts_docs = fts_search(query,k=k)

    # if not fts_docs:
    #     print("[hybrid_search] FTS empty → fallback to simplified query")
    #     simple_query = query.lower().replace(".", " ")
    #     fts_docs = fts_search(simple_query, k=k)

    # SQL (nl2sql)
    try:
        sql_result = nl2sql_query(query)

        sql_answer = sql_result.get("response", {}).get("answer", "")

        sql_docs = []
        if sql_answer.strip():
            sql_docs.append({
                "content": sql_answer,
                "metadata": {
                    "source": "sql",
                    "sql_query": sql_result.get("generated_sql", "")
                }
            })
        print(f"[hybrid_search] SQL docs: {len(sql_docs)}")

    except Exception as e:
        print(f"[hybrid_search] SQL failed: {e}")
        sql_docs = []

    # print(f"[hybrid_search] vector={len(vector_docs)}, fts={len(fts_docs)}, sql = {len(sql_docs)}")
    print(f"[hybrid_search] vector={len(vector_docs)}, sql = {len(sql_docs)}")

    # 4. RRF fusion
    rrf_scores = {}
    chunk_map = {}

    def add_docs(docs, weight_offset=0):
        for rank, doc in enumerate(docs):
            key = hashlib.md5(doc["content"].encode()).hexdigest()
            score = 1 / (60 + rank + 1 + weight_offset)
            rrf_scores[key] = rrf_scores.get(key, 0) + score
            chunk_map[key] = doc

    # Add all sources
    add_docs(vector_docs)
    # add_docs(fts_docs)
    add_docs(sql_docs)

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # Fallback
    if not ranked:
        print("[hybrid_search] No results from any source")
        return [{
            "content": "No relevant documents found",
            "metadata": {"source": "fallback"}
        }]

    return [chunk_map[key] for key, _ in ranked[:k]]




# def hybrid_search_fts_vector(query: str, k: int):
#     vector_docs = vector_search(query, k=k)

#     fts_query = build_or_tsquery(clean_query(query))
#     fts_docs = fts_search(fts_query, k=k)
    

#     if not fts_docs:
#         print("[hybrid_search] FTS empty → fallback to simplified query")
#         simple_query = query.lower().replace(".", " ")
#         fts_docs = fts_search(simple_query, k=k)

#     rrf_scores: dict[str, float] = {}
#     chunk_map: dict[str, dict] = {}

#     #giving ranks starting at 1 for RRF calculation and using the first 120 char
#     for rank, doc in enumerate(vector_docs):
#         # key = doc.page_content[:120]
#         key = hashlib.md5(doc["content"].encode()).hexdigest()
#         rrf_scores[key] = rrf_scores.get(key,0) + 1 / (60+ rank +1)
#         # chunk_map[key] = {"content": doc.page_content, "metadata": doc.metadata}
#         chunk_map[key] = doc

#     for rank, doc in enumerate(fts_docs):
#         # key = item["content"][:120]
#         key = hashlib.md5(doc["content"].encode()).hexdigest()
#         rrf_scores[key] = rrf_scores.get(key,0) + 1 / (60+ rank +1)
#         # chunk_map[key] = {"content": doc.page_content, "metadata": doc.metadata}
#         chunk_map[key] = doc

#     ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
#     if not ranked:
#         return [{
#             "content": "No relevant documents found",
#             "metadata": {"source": "fallback"}
#         }]
#     return [chunk_map[key] for key,_ in ranked[:k]]

    

    #hybrid search
# def hybrid_search_old(state: RAGState) -> RAGState:
#     print("inside hybrid search")

    

#     vector_docs_raw = state.get("vector_docs", [])
#     fts_docs = state.get("fts_docs", [])

#     vector_docs = []

#     for doc in vector_docs_raw:
#         if isinstance(doc, dict) and "content" in doc:
#             vector_docs.append(doc)
#         elif hasattr(doc, "page_content"):
#             vector_docs.append({
#                 "content": doc.page_content,
#                 "metadata": doc.metadata
#             })
#         else:
#             continue

#     rrf_scores = {}
#     chunk_map = {}

#     for rank, doc in enumerate(vector_docs):
#         key = doc["content"][:120]
#         rrf_scores[key] = rrf_scores.get(key, 0) + 1/(60 + rank + 1)
#         chunk_map[key] = doc

#     for rank, doc in enumerate(fts_docs):
#         key = doc["content"][:120]
#         rrf_scores[key] = rrf_scores.get(key, 0) + 1/(60 + rank + 1)
#         chunk_map[key] = doc

#     ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
#     top_k_docs = [chunk_map[key] for key, _ in ranked[:k]]

#     return {**state, "retrieved_docs": top_k_docs}
