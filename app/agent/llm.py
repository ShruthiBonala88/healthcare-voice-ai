"""
Chat + embedding model clients via OpenRouter (OpenAI-compatible API),
wired through langchain-openai so they drop straight into LangChain/
LangGraph chains and tool-calling agents.
"""
from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import get_settings


@lru_cache
def get_chat_model(temperature: float = 0.3) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openrouter_chat_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=temperature,
        default_headers={
            # Recommended by OpenRouter for attribution / rate-limit tiers
            "HTTP-Referer": settings.base_url,
            "X-Title": "Healthcare Voice AI",
        },
    )


@lru_cache
def get_embedding_model() -> OpenAIEmbeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.openrouter_embedding_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
