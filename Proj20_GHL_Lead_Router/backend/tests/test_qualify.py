from app.qualify import tier_from_score, parse_qualification, qualify_lead, build_prompt


def test_tier_from_score_boundaries():
    assert tier_from_score(10) == "hot"
    assert tier_from_score(8) == "hot"
    assert tier_from_score(7) == "warm"
    assert tier_from_score(5) == "warm"
    assert tier_from_score(4) == "cold"
    assert tier_from_score(1) == "cold"


def test_parse_qualification_clamps_a_score_above_ten():
    result = parse_qualification('{"score": 15, "reason": "x", "suggested_reply": "y"}')
    assert result["score"] == 10


def test_parse_qualification_rounds_a_fractional_score():
    result = parse_qualification('{"score": 2.6, "reason": "x", "suggested_reply": "y"}')
    assert result["score"] == 3


def test_parse_qualification_extracts_json_wrapped_in_prose():
    result = parse_qualification('Sure! {"score": 9, "reason": "solid", "suggested_reply": "reply"} Hope that helps.')
    assert result == {"score": 9, "tier": "hot", "reason": "solid", "suggested_reply": "reply"}


def test_parse_qualification_defaults_to_cold_on_no_json():
    result = parse_qualification("no json here")
    assert result["tier"] == "cold"
    assert result["score"] == 1


def test_parse_qualification_defaults_to_cold_on_malformed_json():
    result = parse_qualification("{not valid json")
    assert result["tier"] == "cold"
    assert result["score"] == 1


def test_parse_qualification_defaults_to_cold_when_score_is_missing():
    result = parse_qualification('{"reason": "no score given", "suggested_reply": ""}')
    assert result["tier"] == "cold"
    assert result["score"] == 1


def test_build_prompt_handles_missing_optional_fields_without_crashing():
    prompt = build_prompt({"name": "Tom", "email": "t@example.com", "message": "hi"})
    assert "Tom" in prompt
    assert "not given" in prompt


def test_qualify_lead_calls_the_injected_llm_and_returns_its_parsed_result():
    calls = []

    def fake_llm(prompt):
        calls.append(prompt)
        return '{"score": 6, "reason": "ok", "suggested_reply": "thanks"}'

    result = qualify_lead({"name": "Tom", "email": "t@example.com", "message": "hi"}, fake_llm)
    assert result == {"score": 6, "tier": "warm", "reason": "ok", "suggested_reply": "thanks"}
    assert len(calls) == 1
    assert "Tom" in calls[0]
