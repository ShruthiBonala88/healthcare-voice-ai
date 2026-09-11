from app.agent.prompts import SYSTEM_PROMPT


def test_medical_safety():
    prompt = SYSTEM_PROMPT.format(hospital_name="Test Hospital")

    assert "Never provide medical advice" in prompt
    assert "nurse" in prompt.lower()

    print("\nMedical advice safety: PASSED")


def test_emergency_safety():
    prompt = SYSTEM_PROMPT.format(hospital_name="Test Hospital")

    assert "medical emergency" in prompt
    assert "human handoff tool" in prompt

    print("Emergency safety: PASSED")


def test_self_harm_safety():
    prompt = SYSTEM_PROMPT.format(hospital_name="Test Hospital")

    assert "self-harm" in prompt
    assert "human handoff tool" in prompt

    print("Self-harm safety: PASSED")


def test_human_request():
    prompt = SYSTEM_PROMPT.format(hospital_name="Test Hospital")

    assert 'explicitly asks for a human' in prompt

    print("Human request safety: PASSED")


def test_frustration():
    prompt = SYSTEM_PROMPT.format(hospital_name="Test Hospital")

    assert "frustrated" in prompt
    assert "two failed attempts" in prompt

    print("Frustration safety: PASSED")


if __name__ == "__main__":
    test_medical_safety()
    test_emergency_safety()
    test_self_harm_safety()
    test_human_request()
    test_frustration()

    print("\n========== SAFETY TEST ==========")
    print("SAFETY TEST PASSED")