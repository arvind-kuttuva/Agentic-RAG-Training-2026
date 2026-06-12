from app.core.db import get_vector_store

def retrieve(query: str, k: int = 4) -> list:
    """Return top-k most similar document chunks for a given query"""
    vector_store = get_vector_store(collection_name="hr_support_desk")
    results = vector_store.similarity_search(query, k=k)
    return results

if __name__ == "__main__":
    query = "what is the capital of belgium?"
    docs = retrieve(query, k=4)

    print(f"\nTop {len(docs)} results for: '{query}'\n{'='*60}")
    for i, doc in enumerate(docs, 1):
        print(f"""\n[{i}] Source: {doc.metadata.get('source')} |
            page: {doc.metadata.get('page')}""")
        print(doc.page_content[:400])

## $env:PYTHONPATH=".";uv run .\app\retrieval\retrieval_gemini.py