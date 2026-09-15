"""
Hospital information tool backed by the RAG knowledge base.

This tool answers general hospital questions such as:
- Hospital location
- Working hours
- Parking
- Visiting policy
- Insurance
- Hospital services
- Other general hospital information
"""

from langchain_core.tools import tool

from app.agent.rag import (
    format_context_for_prompt,
    retrieve_hospital_knowledge,
)


@tool
async def hospital_information(question: str) -> str:
    """
    Answer general non-medical questions about the hospital.

    Uses semantic search over the hospital knowledge base.
    """

    if not question or not question.strip():
        raise ValueError("Hospital information question cannot be empty.")

    chunks = await retrieve_hospital_knowledge(question.strip())

    return format_context_for_prompt(chunks)