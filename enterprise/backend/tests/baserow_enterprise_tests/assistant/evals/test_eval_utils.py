from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from pydantic import BaseModel, TypeAdapter, ValidationError

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow_enterprise.assistant.model_profiles import (
    ResolvedAssistantModelProfile,
    resolve_assistant_model,
)
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_enterprise.assistant.tools.toolset import InlineRefsToolset

from .eval_utils import create_eval_assistant


@pytest.mark.django_db
def test_create_eval_assistant_passes_model_and_profile_name(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    provider = AIProviderHandler.create_provider(
        "openai",
        api_key="database-secret",
        models_data=[
            {
                "model_identifier": "database-model",
                "feature_types": [AI_PROVIDER_FEATURE_KUMA],
            }
        ],
    )
    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=provider.models.get(),
    )
    toolset = MagicMock()

    with patch.object(
        assistant_tool_registry,
        "build_toolset",
        return_value=(toolset, "database", "application", "automation", "explain"),
    ) as build_toolset:
        result = create_eval_assistant(user, workspace, model="openai:test-model")

    assert result[-1] is toolset
    assert result[1].tool_helpers.model_profile.model_string == "openai:test-model"
    assert (
        resolve_assistant_model(workspace=workspace).model_string
        == "openai:database-model"
    )
    build_toolset.assert_called_once()
    assert build_toolset.call_args.kwargs == {
        "user": user,
        "workspace": workspace,
        "model": result[3],
        "model_profile": result[1].tool_helpers.model_profile,
        "deps": result[1],
    }
    assert not isinstance(result[3], str)


@pytest.mark.django_db
def test_eval_tool_arg_repair_owns_the_concrete_model_lifecycle(data_fixture):
    """The eval toolset must receive a usable model, not its string identifier."""

    class ToolArgs(BaseModel):
        count: int

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    model = MagicMock()
    model.__aenter__.return_value = model
    model.__aexit__.return_value = None
    inner = MagicMock()

    def build_toolset(**kwargs):
        return (
            InlineRefsToolset(
                inner,
                model=kwargs["model"],
                model_profile=kwargs["model_profile"],
            ),
            "database",
            "application",
            "automation",
            "explain",
        )

    with (
        patch.object(
            ResolvedAssistantModelProfile,
            "create_model",
            return_value=model,
        ),
        patch.object(
            assistant_tool_registry,
            "build_toolset",
            side_effect=build_toolset,
        ),
        patch(
            "pydantic_ai.Agent.run",
            new=AsyncMock(return_value=SimpleNamespace(output='{"count": 2}')),
        ),
    ):
        result = create_eval_assistant(user, workspace, model="openai:test-model")
        toolset = result[-1]
        validator = TypeAdapter(ToolArgs)
        toolset._schemas["example"] = ToolArgs.model_json_schema()
        toolset._original_validators["example"] = validator
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_python({"count": "invalid"})

        fixed = async_to_sync(toolset._fix_tool_args)(
            "example", {"count": "invalid"}, exc_info.value
        )

    assert fixed == ToolArgs(count=2)
    model.__aenter__.assert_awaited_once_with()
    model.__aexit__.assert_awaited_once()
