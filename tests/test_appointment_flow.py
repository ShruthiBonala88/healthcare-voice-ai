import asyncio

from app.agent.graph import run_agent_turn


async def main():
    state = {
        "messages": [],
        "identity_verified": False,
        "patient_id": None,
    }

    conversation = [
        "I want to book an appointment.",
        "I need to see a cardiologist.",
        "My name is John Smith and my date of birth is 15 January 1995.",
        "My phone number is 9876543210.",
        "Yes, please book the available appointment for me.",
    ]

    for message in conversation:
        print("\n========== PATIENT ==========")
        print(message)

        result = await run_agent_turn(
            call_sid="test-appointment-001",
            caller_number="+910000000000",
            user_text=message,
            state=state,
        )

        print("\n========== AGENT ==========")
        print(result["reply"])

        state = result["state"]

    print("\n========== APPOINTMENT FLOW TEST ==========")
    print("Conversation completed.")


if __name__ == "__main__":
    asyncio.run(main())