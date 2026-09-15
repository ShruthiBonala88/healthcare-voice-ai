from pathlib import Path
from typing import Any

from app.agent.llm import get_embedding_model
from app.data.supabase_client import get_supabase


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split text into small chunks for embedding."""

    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])

        if chunk.strip():
            chunks.append(chunk)

    return chunks


def ingest_knowledge(
    text: str,
    metadata: dict[str, Any] | None = None,
    title: str = "Hospital Knowledge",
    source: str = "hospital_knowledge.txt",
) -> int:
    """
    Store hospital knowledge as:

        knowledge_documents
                ↓
        knowledge_chunks
                ↓
        embeddings
    """

    metadata = metadata or {}

    if not text.strip():
        return 0

    chunks = chunk_text(text)

    if not chunks:
        return 0

    embeddings = get_embedding_model()
    supabase = get_supabase()

    # ------------------------------------------------------------
    # STEP 1: Create parent knowledge document
    # ------------------------------------------------------------

    document_response = (
        supabase
        .table("knowledge_documents")
        .insert(
            {
                "title": title,
                "source": source,
                "content": text,
                "metadata": metadata,
            }
        )
        .execute()
    )

    document_rows = document_response.data or []

    if not document_rows:
        raise RuntimeError(
            "Failed to create knowledge document."
        )

    document_id = document_rows[0]["id"]

    # ------------------------------------------------------------
    # STEP 2: Create embeddings for chunks
    # ------------------------------------------------------------

    rows = []

    for chunk in chunks:

        vector = embeddings.embed_query(chunk)

        rows.append(
            {
                "document_id": document_id,
                "content": chunk,
                "metadata": metadata,
                "embedding": vector,
            }
        )

    # ------------------------------------------------------------
    # STEP 3: Insert chunks
    # ------------------------------------------------------------

    if rows:

        supabase \
            .table("knowledge_chunks") \
            .insert(rows) \
            .execute()

    return len(rows)


def ingest_hospital_knowledge() -> int:
    """
    Read hospital knowledge file and ingest it
    into Supabase vector storage.
    """

    knowledge_file = (
        Path(__file__).resolve().parent.parent
        / "knowledge"
        / "hospital_knowledge.txt"
    )

    if not knowledge_file.exists():
        raise FileNotFoundError(
            f"Knowledge file not found: {knowledge_file}"
        )

    text = knowledge_file.read_text(
        encoding="utf-8"
    )

    return ingest_knowledge(
        text=text,
        title="Hospital Knowledge",
        source="hospital_knowledge.txt",
        metadata={
            "source": "hospital_knowledge.txt",
            "type": "hospital_information",
        },
    )


if __name__ == "__main__":

    count = ingest_hospital_knowledge()

    print(
        f"Successfully ingested {count} knowledge chunks."
    )