"""
Chat + embedding model clients via OpenRouter.

OpenRouter provides an OpenAI-compatible API, so these clients
work directly with LangChain and LangGraph.
"""

from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings


@lru_cache
def get_chat_model(temperature: float = 0.3) -> ChatOpenAI:
    """
    Return the shared chat model.

    A small max_tokens value is intentional because Voxevia is a
    phone-based voice agent. The agent should give short,
    conversational responses rather than long answers.
    """

    settings = get_settings()

    return ChatOpenAI(
        model=settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
        max_tokens=500,
        default_headers={
            "HTTP-Referer": settings.base_url,
            "X-Title": "Voxevia Hospital Voice AI",
        },
    )


@lru_cache
def get_embedding_model() -> OpenAIEmbeddings:
    """
    Return the shared embedding model.

    Embeddings are used by the RAG layer to search hospital
    knowledge stored in Supabase/pgvector.
    """

    settings = get_settings()

    return OpenAIEmbeddings(
        model=settings.openrouter_embedding_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )