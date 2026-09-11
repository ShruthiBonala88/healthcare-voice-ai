"""
RAG retriever over the hospital knowledge base stored in Supabase pgvector.
Uses the `match_knowledge_base` Postgres function defined in schema.sql.
"""
from typing import Any

from app.agent.llm import get_embedding_model
from app.data.supabase_client import get_supabase


async def retrieve_hospital_knowledge(query: str, k: int = 4) -> list[dict[str, Any]]:
    """
    Returns a list of {content, metadata, similarity} dicts, most relevant first.
    """
    embeddings = get_embedding_model()
    query_vector = embeddings.embed_query(query)

    supabase = get_supabase()
    response = supabase.rpc(
        "match_knowledge_base",
        {"query_embedding": query_vector, "match_count": k, "filter": {}},
    ).execute()
    return response.data or []


def format_context_for_prompt(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "No relevant hospital information found."
    return "\n\n".join(f"- {c['content']}" for c in chunks)
