"""
RAG retriever over the hospital knowledge base stored in Supabase pgvector.

Uses the `match_knowledge_chunks` Postgres function
defined in schema.sql.
"""

from typing import Any

from app.agent.llm import get_embedding_model
from app.data.supabase_client import get_supabase


async def retrieve_hospital_knowledge(
    query: str,
    k: int = 4,
) -> list[dict[str, Any]]:
    """
    Convert the user's question into an embedding vector
    and retrieve the most relevant hospital knowledge chunks.
    """

    if not query or not query.strip():
        return []

    if k < 1:
        k = 1

    embeddings = get_embedding_model()

    query_vector = embeddings.embed_query(
        query.strip()
    )

    supabase = get_supabase()

    response = (
        supabase
        .rpc(
            "match_knowledge_chunks",
            {
                "query_embedding": query_vector,
                "match_count": k,
            },
        )
        .execute()
    )

    return response.data or []


def format_context_for_prompt(
    chunks: list[dict[str, Any]],
) -> str:
    """
    Convert retrieved knowledge chunks into text
    that can be provided to the LLM.
    """

    if not chunks:
        return "No relevant hospital information found."

    return "\n\n".join(
        f"- {chunk.get('content', '')}"
        for chunk in chunks
        if chunk.get("content")
    )