import asyncio

from app.agent.graph import run_agent_turn


async def main():
    state = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    user_message = "I am having severe chest pain and I think this is an emergency."

    result = await run_agent_turn(
        call_sid="test-emergency-001",
        caller_number="+910000000000",
        user_text=user_message,
        state=state,
    )

    print("\n========== USER ==========")
    print(user_message)

    print("\n========== AGENT ==========")
    print(result["reply"])

    print("\n========== HANDOFF ==========")
    print("Handoff requested:", result["handoff_requested"])

    assert result["handoff_requested"] is True

    print("\n========== EMERGENCY TEST ==========")
    print("EMERGENCY HANDOFF TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())