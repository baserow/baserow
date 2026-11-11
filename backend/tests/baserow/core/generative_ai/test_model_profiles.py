import pytest

from baserow.core.generative_ai.model_profiles import (
    DOCUMENTATION,
    ORCHESTRATOR,
    SUBAGENT,
    get_model_settings,
)


def test_shared_defaults_do_not_apply_kumas_temperature_override(settings):
    settings.BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE = 0.9

    assert get_model_settings("groq:openai/gpt-oss-120b", ORCHESTRATOR) == {
        "temperature": 0.3,
        "timeout": 30,
        "parallel_tool_calls": False,
        "max_tokens": 16384,
    }


@pytest.mark.parametrize(
    "model,has_override",
    [
        ("groq:openai/gpt-oss-120b", True),
        ("groq:gpt-oss-120b", True),
        ("groq:custom/gpt-oss-120b", True),
        ("groq:openai/gpt-oss-20b", False),
        ("openai:openai/gpt-oss-120b", False),
        ("unknown:openai/gpt-oss-120b", False),
        ("gpt-oss-120b", False),
    ],
)
def test_model_overrides_match_provider_and_last_model_segment(model, has_override):
    for role in (SUBAGENT, DOCUMENTATION):
        settings = get_model_settings(model, role)
        assert settings.get("extra_body") == (
            {"reasoning_effort": "high"} if has_override else None
        )
    assert "extra_body" not in get_model_settings(model, ORCHESTRATOR)


def test_settings_mutation_cannot_change_later_requests_or_another_role():
    model = "groq:openai/gpt-oss-120b"
    original = get_model_settings(model, DOCUMENTATION)

    original["temperature"] = 1
    original["extra_body"]["reasoning_effort"] = "low"
    original["timeout"] = 1

    for role in (DOCUMENTATION, SUBAGENT):
        subsequent = get_model_settings(model, role)
        assert subsequent["temperature"] == 0.3
        assert subsequent["extra_body"] == {"reasoning_effort": "high"}
    assert "timeout" not in get_model_settings(model, DOCUMENTATION)
    assert get_model_settings(model, SUBAGENT)["timeout"] == 20


def test_unknown_roles_have_no_request_defaults():
    assert get_model_settings("groq:openai/gpt-oss-120b", "unknown") == {}
