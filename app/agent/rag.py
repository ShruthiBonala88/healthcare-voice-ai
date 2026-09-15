import json
import math
from typing import Any

from app.agent.llm import get_embedding_model
from app.data.supabase_client import get_supabase


def cosine_similarity(query_vector, stored_vector):
    if len(query_vector) != len(stored_vector):
        raise ValueError(
            f"Vector dimension mismatch: "
            f"query={len(query_vector)}, stored={len(stored_vector)}"
        )

    dot = sum(a * b for a, b in zip(query_vector, stored_vector))

    query_norm = math.sqrt(sum(a * a for a in query_vector))
    stored_norm = math.sqrt(sum(a * a for a in stored_vector))

    if query_norm == 0 or stored_norm == 0:
        return 0.0

    return dot / (query_norm * stored_norm)


async def retrieve_hospital_knowledge(
    query: str,
    k: int = 4,
) -> list[dict[str, Any]]:

    print("========== RAG START ==========")
    print("RAG QUERY:", query)

    embedding_model = get_embedding_model()
    query_vector = embedding_model.embed_query(query)

    print("QUERY VECTOR DIMENSION:", len(query_vector))

    supabase = get_supabase()

    response = (
        supabase
        .table("knowledge_chunks")
        .select("id, document_id, content, metadata, embedding")
        .execute()
    )

    rows = response.data or []

    print("DATABASE ROW COUNT:", len(rows))

    results = []

    for row in rows:
        stored_embedding = row.get("embedding")

        print("ROW ID:", row["id"])
        print("EMBEDDING TYPE:", type(stored_embedding))

        if not stored_embedding:
            continue

        stored_vector = json.loads(stored_embedding)

        print("STORED VECTOR DIMENSION:", len(stored_vector))

        similarity = cosine_similarity(
            query_vector,
            stored_vector,
        )

        print("SIMILARITY:", similarity)

        results.append({
            "id": row["id"],
            "document_id": row["document_id"],
            "content": row["content"],
            "metadata": row.get("metadata") or {},
            "similarity": similarity,
        })

    results.sort(
        key=lambda item: item["similarity"],
        reverse=True,
    )

    print("FINAL RESULT COUNT:", len(results))
    print("========== RAG END ==========")

    return results[:k]


def format_context_for_prompt(
    chunks: list[dict[str, Any]],
) -> str:

    if not chunks:
        return "No relevant hospital information found."

    return "\n\n".join(
        f"- {chunk['content']}"
        for chunk in chunks
    )
