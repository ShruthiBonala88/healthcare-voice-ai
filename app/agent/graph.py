
"""
LangGraph agent for Healthcare Voice AI.

Flow:

                    ┌──────────────┐
                    │    AGENT     │
                    │     LLM      │
                    └──────┬───────┘
                           │
                    Tool call?
                     /          \
                   YES           NO
                    │             │
                    ▼             ▼
             ┌─────────────┐    END
             │ POLICY GATE │
             └──────┬──────┘
                    │
              Authorized?
               /          \
             YES           NO
              │             │
              ▼             ▼
          ┌────────┐      AGENT
          │ TOOLS  │
          └───┬────┘
              │
              ▼
            AGENT

run_agent_turn() is the main entrypoint used by the
voice stream handler.
"""

from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

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

from app.tools.patient_tools import (
    create_patient,
    find_patient,
)

from app.tools.identity_tools import (
    verify_patient_identity,
)

from app.tools.policy import (
    PolicyError,
    ToolCallContext,
    authorize_tool_call,
)


logger = get_logger("agent")


# ============================================================
# TOOLS
# ============================================================

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
    verify_patient_identity,
]


# ============================================================
# LLM + TOOL NODE
# ============================================================

_llm = get_chat_model().bind_tools(TOOLS)

_tool_node = ToolNode(TOOLS)


# ============================================================
# AGENT NODE
# ============================================================

def _call_model(state: AgentState) -> dict:
    """
    Call the LLM.

    The LLM receives:
        - System prompt
        - Previous conversation
        - Latest patient message

    It can either:
        1. Return normal text
        2. Request a tool call
    """

    messages = state["messages"]

    # Add system prompt only once.
    if not any(
        isinstance(message, SystemMessage)
        for message in messages
    ):
        messages = [
            SystemMessage(
                content=SYSTEM_PROMPT.format(
                    hospital_name="the hospital"
                )
            )
        ] + messages

    response = _llm.invoke(messages)

    logger.info(
        "agent_model_called",
        extra={
            "has_tool_calls": bool(
                getattr(response, "tool_calls", None)
            )
        },
    )

    return {
        "messages": [response]
    }


# ============================================================
# POLICY GATE
# ============================================================

def _policy_gate(state: AgentState) -> dict:
    """
    Check whether requested tools are allowed.

    IMPORTANT:
    This function MUST always return at least one state field.

    If tool calls are allowed:
        return scratch

    If a tool call is blocked:
        return ToolMessage(s)

    This prevents LangGraph InvalidUpdateError.
    """

    messages = state.get("messages", [])

    if not messages:
        return {
            "scratch": state.get("scratch", {})
        }

    last = messages[-1]

    # --------------------------------------------------------
    # No tool request
    # --------------------------------------------------------

    if not isinstance(last, AIMessage):
        return {
            "scratch": state.get("scratch", {})
        }

    tool_calls = getattr(last, "tool_calls", None)

    if not tool_calls:
        return {
            "scratch": state.get("scratch", {})
        }

    # --------------------------------------------------------
    # Validate every tool call
    # --------------------------------------------------------

    blocked_messages = []

    for call in tool_calls:

        tool_name = call.get("name")
        tool_args = call.get("args", {})
        tool_call_id = call.get("id")

        try:

            authorize_tool_call(
                ToolCallContext(
                    state=state,
                    tool_name=tool_name,
                    tool_args=tool_args,
                )
            )

            logger.info(
                "tool_authorized",
                extra={
                    "tool_name": tool_name,
                },
            )

        except PolicyError as exc:

            logger.warning(
                "tool_blocked",
                extra={
                    "tool_name": tool_name,
                    "reason": str(exc),
                },
            )

            blocked_messages.append(
                ToolMessage(
                    content=f"Blocked: {exc}",
                    tool_call_id=tool_call_id,
                )
            )

    # --------------------------------------------------------
    # At least one tool was blocked
    # --------------------------------------------------------

    if blocked_messages:

        return {
            "messages": blocked_messages
        }

    # --------------------------------------------------------
    # All tools authorized
    # --------------------------------------------------------

    return {
        "scratch": state.get("scratch", {})
    }


# ============================================================
# ROUTE AFTER AGENT
# ============================================================

def _route_after_model(
    state: AgentState,
) -> str:
    """
    Decide whether to execute tools or finish the turn.
    """

    messages = state.get("messages", [])

    if not messages:
        return END

    last = messages[-1]

    if (
        isinstance(last, AIMessage)
        and getattr(last, "tool_calls", None)
    ):
        return "policy_gate"

    return END


# ============================================================
# ROUTE AFTER POLICY
# ============================================================

def _route_after_policy(
    state: AgentState,
) -> str:
    """
    Decide whether policy blocked the tool or
    the tool can actually execute.
    """

    messages = state.get("messages", [])

    if not messages:
        return "agent"

    last = messages[-1]

    # Policy generated a ToolMessage.
    # Send it back to the LLM so the LLM can explain
    # the restriction to the caller.
    if isinstance(last, ToolMessage):
        return "agent"

    # Otherwise execute the requested tools.
    return "tools"


# ============================================================
# BUILD GRAPH
# ============================================================

def build_graph():
    """
    Build and compile the LangGraph workflow.
    """

    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node(
        "agent",
        _call_model,
    )

    graph.add_node(
        "policy_gate",
        _policy_gate,
    )

    graph.add_node(
        "tools",
        _tool_node,
    )

    # --------------------------------------------------------
    # Starting point
    # --------------------------------------------------------

    graph.set_entry_point("agent")

    # --------------------------------------------------------
    # Agent -> Policy Gate OR END
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "agent",
        _route_after_model,
        {
            "policy_gate": "policy_gate",
            END: END,
        },
    )

    # --------------------------------------------------------
    # Policy Gate -> Tools OR Agent
    # --------------------------------------------------------

    graph.add_conditional_edges(
        "policy_gate",
        _route_after_policy,
        {
            "tools": "tools",
            "agent": "agent",
        },
    )

    # --------------------------------------------------------
    # Tools -> Agent
    # --------------------------------------------------------

    graph.add_edge(
        "tools",
        "agent",
    )

    return graph.compile()


# ============================================================
# COMPILED GRAPH
# ============================================================

_compiled_graph = build_graph()


# ============================================================
# RUN ONE AGENT TURN
# ============================================================

async def run_agent_turn(
    call_sid: str,
    caller_number: str,
    user_text: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    Run one complete patient conversation turn.

    Example:

        patient:
            "What departments are available?"

        agent:
            LLM decides whether hospital knowledge/tool
            information is required.

        tool:
            Executes requested tool if authorized.

        agent:
            Generates final response.

    Returns:

        {
            "reply": "...",
            "state": {...},
            "handoff_requested": False
        }
    """

    # --------------------------------------------------------
    # Build graph state
    # --------------------------------------------------------

    previous_messages = state.get(
        "messages",
        [],
    )

    graph_state: AgentState = {
        "messages": previous_messages
        + [
            HumanMessage(
                content=user_text
            )
        ],

        "call_sid": call_sid,

        "caller_number": caller_number,

        "patient_id": state.get(
            "patient_id"
        ),

        "identity_verified": state.get(
            "identity_verified",
            False,
        ),

        "handoff_requested": state.get(
            "handoff_requested",
            False,
        ),

        "scratch": state.get(
            "scratch",
            {},
        ),
    }

    # --------------------------------------------------------
    # Run LangGraph
    # --------------------------------------------------------

    logger.info(
        "agent_turn_started",
        extra={
            "call_sid": call_sid,
            "caller_number": caller_number,
            "user_text": user_text,
        },
    )

    result = await _compiled_graph.ainvoke(
        graph_state
    )

    # --------------------------------------------------------
    # Preserve identity verification
    # --------------------------------------------------------

    if result.get("messages"):

        for message in result["messages"]:

            content = getattr(
                message,
                "content",
                None,
            )

            if (
                isinstance(content, str)
                and '"verified": true'
                in content.lower()
            ):
                result["identity_verified"] = True

    # --------------------------------------------------------
    # Find final AI response
    # --------------------------------------------------------

    reply_text = ""

    for message in reversed(
        result.get("messages", [])
    ):

        if isinstance(
            message,
            AIMessage,
        ):

            # Ignore AI messages that only contain
            # tool calls and have no actual text.
            if (
                isinstance(
                    message.content,
                    str,
                )
                and message.content.strip()
            ):

                reply_text = (
                    message.content.strip()
                )

                break

    # --------------------------------------------------------
    # Detect human handoff
    # --------------------------------------------------------

    handoff_requested = any(
        isinstance(
            message,
            ToolMessage,
        )
        and "handoff_requested"
        in (
            message.content
            or ""
        )
        for message in result.get(
            "messages",
            [],
        )
    )

    # --------------------------------------------------------
    # Fallback response
    # --------------------------------------------------------

    if not reply_text:

        reply_text = (
            "Sorry, could you say that again?"
        )

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    logger.info(
        "agent_turn_finished",
        extra={
            "call_sid": call_sid,
            "handoff_requested": handoff_requested,
        },
    )

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {
        "reply": reply_text,
        "state": result,
        "handoff_requested": handoff_requested,
    }

