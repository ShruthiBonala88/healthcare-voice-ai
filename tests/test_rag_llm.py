import asyncio

from app.agent.llm import get_chat_model
from app.agent.rag import format_context_for_prompt


LOCAL_KNOWLEDGE = [
    {
        "content": "Hospital visiting hours are from 9 AM to 8 PM.",
        "similarity": 0.95,
    },
    {
        "content": "The hospital provides Cardiology, Neurology, Orthopedics and General Medicine departments.",
        "similarity": 0.92,
    },
]


def local_retrieve(query: str, k: int = 1):
    return LOCAL_KNOWLEDGE[:k]


async def test_rag_llm():
    query = "What are the hospital visiting hours?"

    chunks = local_retrieve(query)

    context = format_context_for_prompt(chunks)

    prompt = f"""
Answer the patient's question using only the hospital information below.

Hospital information:
{context}

Patient question:
{query}

Give a short, natural answer suitable for a phone conversation.
Do not invent any information.
"""

    llm = get_chat_model()

    response = await llm.ainvoke(prompt)

    print("\n========== USER QUESTION ==========")
    print(query)

    print("\n========== RAG CONTEXT ==========")
    print(context)

    print("\n========== LLM ANSWER ==========")
    print(response.content)

    assert response.content
    answer = response.content.replace("\u202f", " ")

    assert "9 AM" in answer or "8 PM" in answer
    print("\n========== RAG + LLM TEST ==========")
    print("RAG + LLM TEST PASSED")


if __name__ == "__main__":
    asyncio.run(test_rag_llm())