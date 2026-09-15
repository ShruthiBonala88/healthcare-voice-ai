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

Security principles:
    1. The LLM is not trusted with security-sensitive caller identity.
    2. The caller phone number comes from trusted call/session state.
    3. The verified patient_id comes from trusted call/session state.
    4. The LLM cannot replace the verified patient_id.
    5. Protected appointment operations require verified identity.

Voxevia is a single-hospital system.

There is no tenant or tenant_id concept.
"""

import json
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
from app.tools.identity_tools import verify_patient_identity
from app.tools.patient_tools import create_patient, find_patient

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
    Send the current conversation state to the LLM.

    The hospital system prompt is inserted automatically when one is
    not already present in the conversation.
    """

    messages = state.get("messages", [])

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
        "messages": [response],
    }


# ============================================================
# SECURITY: TRUSTED TOOL ARGUMENTS
# ============================================================


def _secure_tool_arguments(
    state: AgentState,
    tool_name: str,
    tool_args: dict[str, Any],
) -> dict[str, Any]:
    """
    Replace security-sensitive LLM-generated arguments with trusted
    values from the current call/session state.

    The LLM can request a tool, but it must never be trusted to decide
    which caller or verified patient the operation applies to.

    Trusted values:

        caller_number
            Comes from the trusted call/session layer.

        patient_id
            Comes from successful identity verification and is stored
            in trusted agent state.

    Security-sensitive tools:

        verify_patient_identity
            caller_phone is always taken from state["caller_number"].

        find_patient
            patient_id is always taken from state["patient_id"]
            when patient_id is part of the tool arguments.

        book_appointment
            patient_id is always taken from state["patient_id"].

        cancel_appointment
            patient_id is always taken from state["patient_id"].

        reschedule_appointment
            patient_id is always taken from state["patient_id"].

    Returns:
        A copy of the tool arguments with security-sensitive values
        replaced by trusted state values.
    """

    secured_args = dict(tool_args)

    # ========================================================
    # TRUSTED CALLER PHONE NUMBER
    # ========================================================

    if tool_name == "verify_patient_identity":
        caller_number = state.get("caller_number")

        if not caller_number:
            raise PolicyError(
                "Trusted caller phone number is missing from call state."
            )

        # Never trust caller_phone generated by the LLM.
        secured_args["caller_phone"] = caller_number

    # ========================================================
    # TRUSTED VERIFIED PATIENT ID
    # ========================================================

    if tool_name in {
        "find_patient",
        "book_appointment",
        "cancel_appointment",
        "reschedule_appointment",
    }:
        patient_id = state.get("patient_id")

        if not patient_id:
            raise PolicyError(
                "Verified patient ID is missing from call state."
            )

        # Never trust patient_id generated by the LLM.
        #
        # Even if the model tries:
        #
        #     patient_id = "another-patient"
        #
        # it will be replaced by the verified patient ID.
        secured_args["patient_id"] = patient_id

    return secured_args


# ============================================================
# POLICY GATE
# ============================================================


def _policy_gate(state: AgentState) -> dict:
    """
    Validate every requested tool call before execution.

    Security checks include:

    1. Tool must exist in the allow-list.
    2. Protected operations require verified identity.
    3. Protected operations require patient_id.
    4. Security-sensitive arguments are replaced with trusted
       call/session values.
    5. Business rules are validated before execution.

    Security flow:

        LLM tool arguments
                ↓
        security hardening
                ↓
        trusted caller_number
        trusted patient_id
                ↓
        policy authorization
                ↓
        tool execution
    """

    messages = state.get("messages", [])

    if not messages:
        return {
            "scratch": state.get("scratch", {})
        }

    last = messages[-1]

    if not isinstance(last, AIMessage):
        return {
            "scratch": state.get("scratch", {})
        }

    tool_calls = getattr(last, "tool_calls", None)

    if not tool_calls:
        return {
            "scratch": state.get("scratch", {})
        }

    authorized_tool_calls = []
    blocked_messages = []

    for call in tool_calls:

        tool_name = call.get("name")
        original_args = call.get("args", {})
        tool_call_id = call.get("id")

        if not isinstance(original_args, dict):
            original_args = {}

        try:

            # ------------------------------------------------
            # SECURITY HARDENING
            # ------------------------------------------------

            secured_args = _secure_tool_arguments(
                state=state,
                tool_name=tool_name,
                tool_args=original_args,
            )

            # ------------------------------------------------
            # POLICY AUTHORIZATION
            # ------------------------------------------------

            authorize_tool_call(
                ToolCallContext(
                    state=state,
                    tool_name=tool_name,
                    tool_args=secured_args,
                )
            )

            # ------------------------------------------------
            # TOOL CALL IS AUTHORIZED
            # ------------------------------------------------

            authorized_call = dict(call)

            authorized_call["args"] = secured_args

            authorized_tool_calls.append(
                authorized_call
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

        except Exception as exc:

            logger.exception(
                "tool_security_processing_failed",
                extra={
                    "tool_name": tool_name,
                    "error": str(exc),
                },
            )

            blocked_messages.append(
                ToolMessage(
                    content=(
                        "Blocked: security validation failed."
                    ),
                    tool_call_id=tool_call_id,
                )
            )

    # ========================================================
    # BLOCKED CALLS
    # ========================================================

    if blocked_messages and not authorized_tool_calls:
        return {
            "messages": blocked_messages,
        }

    # ========================================================
    # AUTHORIZED CALLS
    # ========================================================

    if authorized_tool_calls:

        secured_ai_message = AIMessage(
            content=last.content,
            tool_calls=authorized_tool_calls,
            additional_kwargs=getattr(
                last,
                "additional_kwargs",
                {},
            ),
            response_metadata=getattr(
                last,
                "response_metadata",
                {},
            ),
            id=last.id,
        )

        result = {
            "messages": [secured_ai_message],
            "scratch": state.get(
                "scratch",
                {},
            ),
        }

        # If some calls were blocked, preserve those
        # security messages as well.
        if blocked_messages:
            result["messages"] = (
                blocked_messages
                + [secured_ai_message]
            )

        return result

    return {
        "scratch": state.get(
            "scratch",
            {},
        )
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

    messages = state.get(
        "messages",
        [],
    )

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
    Decide whether policy blocked the tool or the tool
    can actually execute.
    """

    messages = state.get(
        "messages",
        [],
    )

    if not messages:
        return "agent"

    last = messages[-1]

    if isinstance(
        last,
        ToolMessage,
    ):
        return "agent"

    return "tools"


# ============================================================
# BUILD GRAPH
# ============================================================


def build_graph():
    """
    Build and compile the Voxevia LangGraph workflow.
    """

    graph = StateGraph(
        AgentState
    )

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

    graph.set_entry_point(
        "agent"
    )

    # --------------------------------------------------------
    # Agent → Policy Gate OR END
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
    # Policy Gate → Tools OR Agent
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
    # Tools → Agent
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
# IDENTITY RESULT EXTRACTION
# ============================================================


def _extract_identity_result(
    messages: list[Any],
) -> dict[str, Any]:
    """
    Extract the latest patient identity verification result
    from ToolMessage objects.

    The identity tool intentionally returns only:

        verified
        patient_id
        patient_number
        reason

    No complete patient record should be copied into agent state.
    """

    for message in reversed(messages):

        if not isinstance(
            message,
            ToolMessage,
        ):
            continue

        content = getattr(
            message,
            "content",
            None,
        )

        if not isinstance(
            content,
            str,
        ):
            continue

        try:
            data = json.loads(
                content
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        if not isinstance(
            data,
            dict,
        ):
            continue

        if "verified" not in data:
            continue

        return data

    return {}


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
    Run one complete agent turn.

    The caller's message is appended to the existing conversation
    state.

    LangGraph then executes the LLM/tool loop until a final
    assistant response is produced.

    Security:

        caller_number
            Comes from trusted call/session state.

        patient_id
            Comes from previous successful identity verification.

    The LLM cannot replace either value.
    """

    previous_messages = state.get(
        "messages",
        [],
    )

    graph_state: AgentState = {

        "messages": (
            previous_messages
            + [
                HumanMessage(
                    content=user_text,
                )
            ]
        ),

        "call_sid": call_sid,

        # ----------------------------------------------------
        # TRUSTED CALLER NUMBER
        # ----------------------------------------------------
        #
        # This value comes from the call/session layer.
        # The LLM cannot replace it during identity verification.
        #

        "caller_number": caller_number,

        # ----------------------------------------------------
        # TRUSTED VERIFIED PATIENT ID
        # ----------------------------------------------------
        #
        # This value comes from previous identity verification.
        #
        # If the patient has not yet been verified, this remains
        # None and protected tools will be blocked by policy.
        #

        "patient_id": state.get(
            "patient_id",
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

    logger.info(
        "agent_turn_started",
        extra={
            "call_sid": call_sid,
        },
    )

    result = await _compiled_graph.ainvoke(
        graph_state,
    )

    result_messages = result.get(
        "messages",
        [],
    )

    # ========================================================
    # PRESERVE IDENTITY VERIFICATION
    # ========================================================

    identity_result = _extract_identity_result(
        result_messages,
    )

    if identity_result.get(
        "verified"
    ) is True:

        result[
            "identity_verified"
        ] = True

        patient_id = identity_result.get(
            "patient_id"
        )

        patient_number = identity_result.get(
            "patient_number"
        )

        if patient_id:

            result[
                "patient_id"
            ] = patient_id

        if patient_number:

            scratch = result.get(
                "scratch",
                {},
            ).copy()

            scratch[
                "patient_number"
            ] = patient_number

            result[
                "scratch"
            ] = scratch

        logger.info(
            "patient_identity_verified",
            extra={
                "call_sid": call_sid,
                "patient_id": patient_id,
            },
        )

    elif identity_result.get(
        "verified"
    ) is False:

        logger.warning(
            "patient_identity_verification_failed",
            extra={
                "call_sid": call_sid,
                "reason": identity_result.get(
                    "reason"
                ),
            },
        )

    # ========================================================
    # FIND FINAL AI RESPONSE
    # ========================================================

    reply_text = ""

    for message in reversed(
        result_messages
    ):

        if not isinstance(
            message,
            AIMessage,
        ):
            continue

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

    # ========================================================
    # DETECT HUMAN HANDOFF
    # ========================================================

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

        for message in result_messages
    )

    if handoff_requested:

        result[
            "handoff_requested"
        ] = True

    # ========================================================
    # FALLBACK RESPONSE
    # ========================================================

    if not reply_text:

        reply_text = (
            "Sorry, could you say that again?"
        )

    # ========================================================
    # LOGGING
    # ========================================================

    logger.info(
        "agent_turn_finished",
        extra={
            "call_sid": call_sid,

            "handoff_requested":
                handoff_requested,

            "identity_verified":
                result.get(
                    "identity_verified",
                    False,
                ),

            "patient_id_present":
                bool(
                    result.get(
                        "patient_id"
                    )
                ),
        },
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "reply": reply_text,

        "state": result,

        "handoff_requested":
            handoff_requested,
    }
