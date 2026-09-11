"""
Hospital knowledge ingestion.

Takes hospital knowledge text, creates embeddings using
the configured OpenRouter embedding model, and stores
documents + chunks in Supabase pgvector.
"""

from typing import Any

from app.agent.llm import get_embedding_model
from app.data.supabase_client import get_supabase


def split_text(text: str, chunk_size: int = 500) -> list[str]:
    """
    Split hospital knowledge into small text chunks.

    We keep this simple for the first version.
    Later we can use a more advanced text splitter.
    """

    text = text.strip()

    if not text:
        return []

    chunks = []

    for start in range(0, len(text), chunk_size):
        chunk = text[start:start + chunk_size].strip()

        if chunk:
            chunks.append(chunk)

    return chunks


def ingest_knowledge(
    title: str,
    content: str,
    source: str = "hospital",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Store hospital knowledge and its embeddings.

    Process:

    1. Create knowledge document
    2. Split content into chunks
    3. Generate embeddings
    4. Store chunks + vectors
    """

    if not title.strip():
        raise ValueError("Knowledge title cannot be empty.")

    if not content.strip():
        raise ValueError("Knowledge content cannot be empty.")

    supabase = get_supabase()
    embeddings = get_embedding_model()

    document_response = (
        supabase
        .table("knowledge_documents")
        .insert(
            {
                "title": title.strip(),
                "source": source,
                "content": content.strip(),
                "metadata": metadata or {},
            }
        )
        .execute()
    )

    if not document_response.data:
        raise RuntimeError(
            "Failed to create knowledge document."
        )

    document = document_response.data[0]
    document_id = document["id"]

    chunks = split_text(content)

    stored_chunks = []

    for chunk in chunks:

        embedding = embeddings.embed_query(chunk)

        chunk_response = (
            supabase
            .table("knowledge_chunks")
            .insert(
                {
                    "document_id": document_id,
                    "content": chunk,
                    "embedding": embedding,
                    "metadata": metadata or {},
                }
            )
            .execute()
        )

        if chunk_response.data:
            stored_chunks.append(
                chunk_response.data[0]
            )

    return {
        "success": True,
        "document_id": document_id,
        "title": title,
        "chunks_created": len(stored_chunks),
    }