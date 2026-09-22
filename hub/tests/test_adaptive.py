from hub.adaptive import AdaptiveCallError, build_kwargs, call_adaptive, has_param


def compliance_v1(asset_id, brand, platform, region, body_text):
    return {"asset_id": asset_id, "brand": brand, "tier": "highly_recommended"}


def compliance_v2(text, asset_type, market="Singapore"):
    return {"score": 90}


def decision_v1(asset_id, decision, reviewer, tag=None, note=None):
    return "ok"


def test_maps_aliases_regardless_of_exact_names():
    values = {"asset_id": "1", "brand": "Jade", "platform": "LinkedIn", "region": "Singapore", "body_text": "hi"}
    result = call_adaptive(compliance_v1, values)
    assert result["tier"] == "highly_recommended"


def test_maps_differently_named_params_via_aliases():
    values = {"body_text": "hi", "content_type": "caption", "region": "Malaysia"}
    result = call_adaptive(compliance_v2, values)
    assert result == {"score": 90}


def test_defaults_are_not_required():
    kwargs, missing = build_kwargs(compliance_v2, {"body_text": "hi", "content_type": "caption"})
    assert missing == [] and "market" not in kwargs


def test_missing_required_param_raises_clear_error():
    try:
        call_adaptive(compliance_v1, {"asset_id": "1", "brand": "Jade"})
    except AdaptiveCallError as exc:
        assert "platform" in str(exc) and "region" in str(exc) and "body_text" in str(exc)
        return
    raise AssertionError("expected AdaptiveCallError")


def test_has_param_detects_canonical_names():
    assert has_param(decision_v1, "asset_id") and has_param(decision_v1, "reviewer")
    assert not has_param(decision_v1, "edited_text")
