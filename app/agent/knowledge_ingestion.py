from pathlib import Path
from typing import Any

from app.agent.llm import get_embedding_model
from app.data.supabase_client import get_supabase


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split text into small chunks for embedding."""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))

    return chunks


def ingest_knowledge(
    text: str,
    metadata: dict[str, Any] | None = None,
) -> int:
    """Create embeddings and store knowledge chunks."""

    metadata = metadata or {}

    chunks = chunk_text(text)

    embeddings = get_embedding_model()
    supabase = get_supabase()

    rows = []

    for chunk in chunks:
        vector = embeddings.embed_query(chunk)

        rows.append(
            {
                "content": chunk,
                "metadata": metadata,
                "embedding": vector,
            }
        )

    if rows:
        supabase.table("knowledge_base").insert(rows).execute()

    return len(rows)


def ingest_hospital_knowledge() -> int:
    """Read hospital knowledge file and ingest it into the vector database."""

    knowledge_file = (
        Path(__file__).resolve().parent.parent
        / "knowledge"
        / "hospital_knowledge.txt"
    )

    text = knowledge_file.read_text(encoding="utf-8")

    return ingest_knowledge(
        text,
        metadata={
            "source": "hospital_knowledge.txt",
            "type": "hospital_information",
        },
    )


if __name__ == "__main__":
    count = ingest_hospital_knowledge()
    print(f"Successfully ingested {count} knowledge chunks.")