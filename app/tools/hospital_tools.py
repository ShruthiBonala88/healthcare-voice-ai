"""
General hospital information tool backed by the RAG knowledge base.
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
    chunks = await retrieve_hospital_knowledge(question)
    return format_context_for_prompt(chunks)