<<<<<<< HEAD

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
=======
"""
LangGraph agent for Voxevia.

The graph implements a single ReAct-style loop:

    User message
        ↓
    LLM
        ↓
    Policy gate
        ↓
    Tools
        ↓
    LLM
        ↓
    Final response

Every tool call passes through the policy gate before execution.
"""
>>>>>>> 6928a2c (Complete backend security validation and tests)

from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
<<<<<<< HEAD

=======
>>>>>>> 6928a2c (Complete backend security validation and tests)
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
<<<<<<< HEAD
<<<<<<< Updated upstream
from app.tools.patient_tools import create_patient, find_patient
from app.tools.identity_tools import verify_patient_identity
from app.tools.policy import PolicyError, ToolCallContext, authorize_tool_call
=======

from app.tools.patient_tools import (
    create_patient,
    find_patient,
)

from app.tools.identity_tools import (
    verify_patient_identity,
)

=======
from app.tools.identity_tools import verify_patient_identity
from app.tools.patient_tools import create_patient, find_patient
>>>>>>> 6928a2c (Complete backend security validation and tests)
from app.tools.policy import (
    PolicyError,
    ToolCallContext,
    authorize_tool_call,
)

<<<<<<< HEAD
>>>>>>> Stashed changes
=======
>>>>>>> 6928a2c (Complete backend security validation and tests)

logger = get_logger("agent")


<<<<<<< HEAD
# ============================================================
# TOOLS
# ============================================================
=======
# ---------------------------------------------------------------------------
# Tools available to the LangGraph agent
# ---------------------------------------------------------------------------
>>>>>>> 6928a2c (Complete backend security validation and tests)

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
<<<<<<< HEAD
<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
]


# ============================================================
# LLM + TOOL NODE
# ============================================================
=======
]


# ---------------------------------------------------------------------------
# LLM + ToolNode
# ---------------------------------------------------------------------------
>>>>>>> 6928a2c (Complete backend security validation and tests)

_llm = get_chat_model().bind_tools(TOOLS)

_tool_node = ToolNode(TOOLS)


<<<<<<< HEAD
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
=======
# ---------------------------------------------------------------------------
# Agent node
# ---------------------------------------------------------------------------

def _call_model(state: AgentState) -> dict:
    """
    Send the current conversation state to the LLM.

    The hospital system prompt is inserted automatically when one is
    not already present in the conversation.
>>>>>>> 6928a2c (Complete backend security validation and tests)
    """

    messages = state["messages"]

<<<<<<< HEAD
    # Add system prompt only once.
    if not any(
        isinstance(message, SystemMessage)
        for message in messages
    ):
=======
    if not any(isinstance(message, SystemMessage) for message in messages):
>>>>>>> 6928a2c (Complete backend security validation and tests)
        messages = [
            SystemMessage(
                content=SYSTEM_PROMPT.format(
                    hospital_name="the hospital"
                )
            )
        ] + messages

    response = _llm.invoke(messages)

<<<<<<< HEAD
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
<<<<<<< Updated upstream
    last = state["messages"][-1]
=======

    messages = state.get("messages", [])

    if not messages:
        return {
            "scratch": state.get("scratch", {})
        }

    last = messages[-1]
>>>>>>> Stashed changes

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
=======
    return {
        "messages": [response],
    }


# ---------------------------------------------------------------------------
# Policy gate
# ---------------------------------------------------------------------------

def _policy_gate(state: AgentState) -> dict:
    """
    Validate every tool call before the tool is executed.

    Protected operations such as booking, cancellation, and rescheduling
    must pass the policy checks first.

    If a tool call is blocked, a ToolMessage is returned to the agent so
    the LLM can respond safely instead of executing the tool.
    """

    last = state["messages"][-1]

    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {}
>>>>>>> 6928a2c (Complete backend security validation and tests)

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

<<<<<<< HEAD
            logger.info(
                "tool_authorized",
                extra={
                    "tool_name": tool_name,
                },
            )

=======
>>>>>>> 6928a2c (Complete backend security validation and tests)
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
<<<<<<< HEAD

<<<<<<< Updated upstream
    return {"scratch": state.get("scratch", {})}
=======
        return {
            "messages": blocked_messages
        }
>>>>>>> Stashed changes

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
=======
        return {
            "messages": blocked_messages,
        }

    return {}


# ---------------------------------------------------------------------------
# Routing after LLM
# ---------------------------------------------------------------------------

def _route_after_model(state: AgentState) -> str:
    """
    Decide whether the agent should execute tools or finish the turn.
    """

    last = state["messages"][-1]

    if isinstance(last, AIMessage) and last.tool_calls:
>>>>>>> 6928a2c (Complete backend security validation and tests)
        return "policy_gate"

    return END


<<<<<<< HEAD
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
=======
# ---------------------------------------------------------------------------
# Routing after policy gate
# ---------------------------------------------------------------------------

def _route_after_policy(state: AgentState) -> str:
    """
    If the policy gate produced a ToolMessage, return to the agent so it
    can explain the restriction.

    Otherwise execute the requested tools.
    """

    last = state["messages"][-1]

    if isinstance(last, ToolMessage):
        return "agent"

    return "tools"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_graph():
    """
    Build and compile the Voxevia LangGraph workflow.
>>>>>>> 6928a2c (Complete backend security validation and tests)
    """

    graph = StateGraph(AgentState)

<<<<<<< HEAD
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

=======
    graph.add_node("agent", _call_model)
    graph.add_node("policy_gate", _policy_gate)
    graph.add_node("tools", _tool_node)

    graph.set_entry_point("agent")

>>>>>>> 6928a2c (Complete backend security validation and tests)
    graph.add_conditional_edges(
        "agent",
        _route_after_model,
        {
            "policy_gate": "policy_gate",
            END: END,
        },
    )

<<<<<<< HEAD
    # --------------------------------------------------------
    # Policy Gate -> Tools OR Agent
    # --------------------------------------------------------

=======
>>>>>>> 6928a2c (Complete backend security validation and tests)
    graph.add_conditional_edges(
        "policy_gate",
        _route_after_policy,
        {
            "tools": "tools",
            "agent": "agent",
        },
    )

<<<<<<< HEAD
    # --------------------------------------------------------
    # Tools -> Agent
    # --------------------------------------------------------

    graph.add_edge(
        "tools",
        "agent",
    )
=======
    graph.add_edge("tools", "agent")
>>>>>>> 6928a2c (Complete backend security validation and tests)

    return graph.compile()


# ============================================================
# COMPILED GRAPH
# ============================================================

_compiled_graph = build_graph()


<<<<<<< HEAD
# ============================================================
# RUN ONE AGENT TURN
# ============================================================
=======
# ---------------------------------------------------------------------------
# Public agent entrypoint
# ---------------------------------------------------------------------------
>>>>>>> 6928a2c (Complete backend security validation and tests)

async def run_agent_turn(
    call_sid: str,
    caller_number: str,
    user_text: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """
<<<<<<< HEAD
    Run one complete patient conversation turn.
=======
    Run one complete agent turn.

    The caller's message is appended to the existing conversation state.
    LangGraph then executes the LLM/tool loop until a final assistant
    response is produced.

    Returns:
        reply:
            Final text response for the caller.

        state:
            Updated LangGraph state to persist for the next turn.

        handoff_requested:
            Whether a human handoff was requested during this turn.
    """

    graph_state: AgentState = {
        "messages": state.get("messages", [])
        + [HumanMessage(content=user_text)],

        "call_sid": call_sid,
        "caller_number": caller_number,

        "patient_id": state.get("patient_id"),

        "identity_verified": state.get(
            "identity_verified",
            False,
        ),

        "handoff_requested": False,

        "scratch": state.get(
            "scratch",
            {},
        ),
    }
>>>>>>> 6928a2c (Complete backend security validation and tests)

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

<<<<<<< Updated upstream
    result = await _compiled_graph.ainvoke(graph_state)
<<<<<<< HEAD
    if result.get("messages"):
        for message in result["messages"]:
            if hasattr(message, "content") and isinstance(message.content, str):
                if '"verified": true' in message.content.lower():
                    result["identity_verified"] = True
=======
    # --------------------------------------------------------
    # Build graph state
    # --------------------------------------------------------
>>>>>>> Stashed changes

    previous_messages = state.get(
        "messages",
        [],
=======

    # -----------------------------------------------------------------------
    # Identity verification result handling
    # -----------------------------------------------------------------------
    #
    # The identity tool may return a serialized result containing:
    #
    #     "verified": true
    #
    # When that happens, preserve the verified state for the next turn.
    #
    # This allows a successful identity verification to unlock protected
    # appointment operations later in the conversation.
    # -----------------------------------------------------------------------

    if result.get("messages"):
        for message in result["messages"]:
            if (
                hasattr(message, "content")
                and isinstance(message.content, str)
                and '"verified": true' in message.content.lower()
            ):
                result["identity_verified"] = True

    # -----------------------------------------------------------------------
    # Extract final response
    # -----------------------------------------------------------------------

    final_message = result["messages"][-1]

    if isinstance(final_message, AIMessage):
        reply_text = final_message.content
    else:
        reply_text = ""

    # -----------------------------------------------------------------------
    # Detect human handoff
    # -----------------------------------------------------------------------

    handoff_requested = any(
        isinstance(message, ToolMessage)
        and "handoff_requested" in (message.content or "")
        for message in result["messages"][-4:]
>>>>>>> 6928a2c (Complete backend security validation and tests)
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
<<<<<<< HEAD
    }

=======
    }
>>>>>>> 6928a2c (Complete backend security validation and tests)
