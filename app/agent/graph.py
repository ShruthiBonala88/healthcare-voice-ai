"""
LangGraph agent: a single ReAct-style loop (LLM <-> tools) with a policy
gate in front of every tool execution, plus routing to end-of-turn once
the model produces a plain-text reply with no further tool calls.

run_agent_turn() is the single entrypoint called by the voice stream
handler for each caller utterance.
"""
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.llm import get_chat_model
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState
from app.observability.logging_config import get_logger
from app.tools.appointment_tools import (
    book_appointment,
    cancel_appointment,
    get_available_slots,
    get_departments,
    get_doctor_details,
    get_doctors,
    reschedule_appointment,
)
from app.tools.hospital_tools import hospital_information
from app.tools.human_handoff import human_handoff
from app.tools.patient_tools import create_patient, find_patient
from app.tools.policy import PolicyError, ToolCallContext, authorize_tool_call

logger = get_logger("agent")

TOOLS = [
    get_departments,
    get_doctors,
    get_doctor_details,
    get_available_slots,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    find_patient,
    create_patient,
    hospital_information,
    human_handoff,
]

_llm = get_chat_model().bind_tools(TOOLS)
_tool_node = ToolNode(TOOLS)


def _call_model(state: AgentState) -> dict:
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [
            SystemMessage(content=SYSTEM_PROMPT.format(hospital_name="the hospital"))
        ] + messages
    response = _llm.invoke(messages)
    return {"messages": [response]}


def _policy_gate(state: AgentState) -> dict:
    """
    Runs before tool execution: validates every requested tool call
    against app/tools/policy.py and short-circuits with a ToolMessage
    error if any call is blocked, instead of hitting the data layer.
    """
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {}

    blocked_messages = []
    for call in last.tool_calls:
        try:
            authorize_tool_call(
                ToolCallContext(state=state, tool_name=call["name"], tool_args=call["args"])
            )
        except PolicyError as exc:
            blocked_messages.append(
                ToolMessage(content=f"Blocked: {exc}", tool_call_id=call["id"])
            )

    if blocked_messages:
        # Remove the blocked calls from further execution by short-circuiting
        # straight back to the model with the policy explanation.
        return {"messages": blocked_messages}
    return {}


def _route_after_model(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "policy_gate"
    return END


def _route_after_policy(state: AgentState) -> str:
    last = state["messages"][-1]
    # If the policy gate already answered with ToolMessages, skip execution
    if isinstance(last, ToolMessage):
        return "agent"
    return "tools"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", _call_model)
    graph.add_node("policy_gate", _policy_gate)
    graph.add_node("tools", _tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _route_after_model, {"policy_gate": "policy_gate", END: END})
    graph.add_conditional_edges("policy_gate", _route_after_policy, {"tools": "tools", "agent": "agent"})
    graph.add_edge("tools", "agent")

    return graph.compile()


_compiled_graph = build_graph()


async def run_agent_turn(
    call_sid: str,
    caller_number: str,
    user_text: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Runs one turn of the conversation: appends the caller's utterance,
    invokes the graph until it produces a final text reply, and returns
    the reply text plus the updated state to persist for the next turn.
    """
    graph_state: AgentState = {
        "messages": state.get("messages", []) + [HumanMessage(content=user_text)],
        "call_sid": call_sid,
        "caller_number": caller_number,
        "patient_id": state.get("patient_id"),
        "identity_verified": state.get("identity_verified", False),
        "handoff_requested": False,
        "scratch": state.get("scratch", {}),
    }

    result = await _compiled_graph.ainvoke(graph_state)

    final_message = result["messages"][-1]
    reply_text = final_message.content if isinstance(final_message, AIMessage) else ""

    handoff_requested = any(
        isinstance(m, ToolMessage) and "handoff_requested" in (m.content or "")
        for m in result["messages"][-4:]
    )

    return {
        "reply": reply_text or "Sorry, could you say that again?",
        "state": result,
        "handoff_requested": handoff_requested,
    }
