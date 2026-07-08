from canitplaydoom.agent import build_prompt, parse_action

ALLOWED = ["turn_left", "turn_right", "attack"]


def test_parse_strict_json():
    action, ok = parse_action('{"action": "attack"}', ALLOWED, "turn_left")
    assert action == "attack" and ok is True


def test_parse_json_with_extra_text():
    text = 'I will attack now. {"action": "attack", "reason": "enemy ahead"}'
    action, ok = parse_action(text, ALLOWED, "turn_left")
    assert action == "attack" and ok is True


def test_parse_keyword_fallback():
    action, ok = parse_action("I think I should turn_right here", ALLOWED, "turn_left")
    assert action == "turn_right" and ok is True


def test_parse_failure_uses_default():
    action, ok = parse_action("no idea", ALLOWED, "turn_left")
    assert action == "turn_left" and ok is False


def test_parse_empty():
    action, ok = parse_action("", ALLOWED, "turn_left")
    assert action == "turn_left" and ok is False


def test_build_prompt_contains_actions_and_legend():
    prompt = build_prompt("....\n....", {".": "floor"}, ALLOWED)
    assert "turn_left" in prompt and "attack" in prompt
    assert "floor" in prompt
