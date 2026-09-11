from app.agent.rag import format_context_for_prompt


LOCAL_KNOWLEDGE = [
    {
        "content": "Hospital visiting hours are from 9 AM to 8 PM.",
        "metadata": {"topic": "visiting_hours"},
        "similarity": 0.95,
    },
    {
        "content": "The hospital provides Cardiology, Neurology, Orthopedics and General Medicine departments.",
        "metadata": {"topic": "departments"},
        "similarity": 0.92,
    },
    {
        "content": "Outpatient consultation is available from 10 AM to 5 PM.",
        "metadata": {"topic": "consultation"},
        "similarity": 0.89,
    },
]


def local_retrieve(query: str, k: int = 2):
    query = query.lower()

    results = []

    for item in LOCAL_KNOWLEDGE:
        if any(word in item["content"].lower() for word in query.split()):
            results.append(item)

    return results[:k]


def test_rag():
    query = "What are the hospital visiting hours?"

    chunks = local_retrieve(query)

    context = format_context_for_prompt(chunks)

    print("\n========== USER QUERY ==========")
    print(query)

    print("\n========== RETRIEVED CONTEXT ==========")
    print(context)

    assert chunks
    assert "visiting hours" in context.lower()

    print("\n========== RAG TEST ==========")
    print("RAG retrieval test PASSED")


if __name__ == "__main__":
    test_rag()