"""
LangGraph conversation state schema.
"""
from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    call_sid: str
    caller_number: str
    patient_id: Optional[str]
    identity_verified: bool
    handoff_requested: bool
    scratch: dict[str, Any]  # free-form working memory for the current turn
