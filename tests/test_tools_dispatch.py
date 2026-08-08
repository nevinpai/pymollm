from pymollm.tools import ASK_USER, dispatch


def test_ask_user_pauses():
    status, payload = dispatch(
        "ask_user",
        {"question": "Which PDB?", "choices": ["1A19", "1BTA"]},
    )
    assert status == ASK_USER
    assert payload["question"] == "Which PDB?"
    assert payload["choices"] == ["1A19", "1BTA"]


def test_unknown_tool():
    status, payload = dispatch("nope", {})
    assert status == "error"
    assert "Unknown" in payload["error"]
