import re
from app.db.db import get_vector_store
import os
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

from langchain.agents import create_agent
from langchain_core.tools import tool
from app.prompts.systemprompts import RAG_SYSTEM_PROMPT
# from langchain_openai import ChatOpenAI
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

#PGVector connection string uses SQLA1chemy format: postgresql+psycopg://...
#pyscopg connect needs standard format: postgresql://..
_raw_conn = os.getenv("PG_CONNECTION_STRING", "").replace("postgresql+psycopg", "postgresql")


# Patterns that signal a precise keyword lookup is needed
_KEYWORD_PATTERNS = [
   r"[A-Z]{2,}-\d{4}-\w+",   # policy/ticket codes: POL-2024-HR-007
   r"\b[A-Z]{2,5}\b",         # short uppercase abbreviations: LTA, CTC, ESI
   r"\d{6,}",                 # long numeric IDs / employee numbers
]
_KEYWORD_RE = re.compile("|".join(_KEYWORD_PATTERNS))

#fts search
@tool()
def fts_search(query: str, k: int=5, collection_name: str = os.getenv("PG_COLLECTION_NAME")) -> list[dict]:
    """full text search for abbreviations and queries that match the regular expression patterns"""
    print("inside fts_search")
    sql = """
       SELECT
           e.document                                               AS content,
           e.cmetadata                                              AS metadata,
           ts_rank(
               to_tsvector('english', e.document),
               plainto_tsquery('english', %(query)s)
           )                                                        AS fts_rank
       FROM  langchain_pg_embedding  e
       JOIN  langchain_pg_collection c ON c.uuid = e.collection_id
       WHERE c.name = %(collection)s
         AND to_tsvector('english', e.document)
             @@ plainto_tsquery('english', %(query)s)
       ORDER BY fts_rank DESC
       LIMIT %(k)s;
    """
    with psycopg.connect(_raw_conn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"query": query,
                            "collection": collection_name,
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

#hybrid search
@tool()
def _hybrid_search(query: str, k: int = 5) -> list[dict]:
    """ combination of vector_search and full text search"""
    print("inside hybrid search")
    vector_store = get_vector_store()
    vector_docs = vector_store.similarity_search(query, k=k)
    fts_docs = fts_search(query, k=k)

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    #giving ranks starting at 1 for RRF calculation and using the first 120 char
    for rank, doc in enumerate(vector_docs):
        key = doc.page_content[:120]
        rrf_scores[key] = rrf_scores.get(key,0) + 1 / (60+ rank +1)
        chunk_map[key] = {"content": doc.page_content, "metadata": doc.metadata}

    for rank, item in enumerate(fts_docs):
        key = item["content"][:120]
        rrf_scores[key] = rrf_scores.get(key,0) + 1 / (60+ rank +1)
        # chunk_map[key] = {"content": doc.page_content, "metadata": doc.metadata}
        chunk_map[key] = {"content": item[content],"metadata": item[metadata]}

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk_map[key] for key,_ in ranked[:k]]


#vector search
@tool()
def vector_search(query: str,k: int = 3) -> list[dict]:
    """ go to the vector store and get the details"""
    print("inside vector search")
    vector_store = get_vector_store()
    docs = vector_store.similarity_search(query, k=k)    
    return [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GOOGLE_MODEL"),
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2)

def rag_assistant(query: str):
    print("inside rag assistant")    
    my_agent = create_agent(
        model=llm, #brain
        tools =[vector_search, fts_search, _hybrid_search ], #register the tool. Its an array as it can have many tools
        system_prompt = RAG_SYSTEM_PROMPT          
    )
    
    response = my_agent.invoke(
        {
            "messages": [
                {
                    "role": "user", 
                    "content": f"Generate RAG based response ffor the query {query}"
                }
            ]
        }
    )
    print(f"inside rag_assitant returning {response}")
    return response["messages"][-1].text

if __name__ == "__main__":
    query = "what is the leave policy for employees?"
    results = query_documents(query, k=5)
    
    print(f"\nTop {len(results)} results for: '{query}'\n{'='*60}")
    for i, item in enumerate(results, 1):
        metadata = item["metadata"]
        print(f"""\n[{i}] Source: {metadata.get('source')} |
            page: {metadata.get('page')}""")
        print(item["content"][:400])





