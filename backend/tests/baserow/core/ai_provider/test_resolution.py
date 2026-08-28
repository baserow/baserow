from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.ai_provider.constants import (
    AI_PROVIDER_FEATURE_KUMA,
    AI_PROVIDER_FEATURE_MODE_MODEL,
)
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import (
    AIProviderConfig,
    AIProviderModel,
    AIProviderWorkspaceOverride,
)
from baserow.core.ai_provider.resolution import get_ai_provider_state
from baserow.core.cache import local_cache
from baserow.core.generative_ai.generative_ai_model_types import (
    GoogleGenerativeAIModelType,
    GroqGenerativeAIModelType,
    OpenAIGenerativeAIModelType,
)


@pytest.mark.django_db
def test_database_provider_is_ignored_while_feature_flag_is_disabled(settings):
    settings.FEATURE_FLAGS = []
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key() == "environment-key"
    assert model_type.get_enabled_models() == ["environment-model"]


@pytest.mark.parametrize(
    "model_type_class",
    [GoogleGenerativeAIModelType, GroqGenerativeAIModelType],
)
def test_google_and_groq_have_no_environment_fallbacks(settings, model_type_class):
    settings.FEATURE_FLAGS = []

    model_type = model_type_class()

    assert model_type.get_api_key() is None
    assert model_type.get_enabled_models() == []


@pytest.mark.django_db
def test_database_provider_is_authoritative_when_enabled(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="disabled-model",
        is_enabled=False,
    )

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key() == "database-key"
    assert model_type.get_enabled_models() == ["database-model"]

    provider.api_key = ""
    provider.is_active = False
    provider.save(update_fields=("api_key", "is_active"))
    local_cache.clear()
    assert model_type.get_api_key() is None
    assert model_type.get_enabled_models() == []


@pytest.mark.django_db
def test_models_can_be_reserved_for_individual_ai_features(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="shared-model",
        feature_types=["ai_fields", "kuma"],
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="kuma-only-model",
        feature_types=["kuma"],
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="ai-field-only-model",
        feature_types=["ai_fields"],
    )

    model_type = OpenAIGenerativeAIModelType()

    assert model_type.get_enabled_models(feature_type="ai_fields") == [
        "shared-model",
        "ai-field-only-model",
    ]
    assert model_type.get_enabled_models(feature_type="kuma") == [
        "shared-model",
        "kuma-only-model",
    ]


@pytest.mark.django_db
def test_one_loaded_state_answers_every_question_without_more_queries(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    model_type = OpenAIGenerativeAIModelType()

    with CaptureQueriesContext(connection) as load_queries:
        state = get_ai_provider_state()

    with CaptureQueriesContext(connection) as resolve_queries:
        assert model_type.get_api_key(state=state) == "database-key"
        assert model_type.get_enabled_models(state=state) == ["database-model"]
        assert model_type.get_api_key(state=state) == "database-key"

    assert len(load_queries) == 3
    assert len(resolve_queries) == 0


@pytest.mark.django_db
def test_provider_state_reflects_handler_mutations(data_fixture, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()

    assert get_ai_provider_state(workspace).instance_providers == {}

    provider = AIProviderHandler.create_provider("openai", api_key="instance-key")
    state = get_ai_provider_state(workspace)
    assert state.instance_providers["openai"].id == provider.id

    model = AIProviderHandler.create_model(
        provider,
        model_identifier="kuma-model",
        feature_types=[AI_PROVIDER_FEATURE_KUMA],
    )
    state = get_ai_provider_state(workspace)
    assert [
        m.model_identifier for m in state.instance_providers["openai"].models.all()
    ] == ["kuma-model"]

    AIProviderHandler.set_workspace_provider_enabled(
        workspace, provider, is_enabled=False
    )
    assert (
        provider.id in get_ai_provider_state(workspace).disabled_instance_provider_ids
    )
    AIProviderHandler.set_workspace_provider_enabled(
        workspace, provider, is_enabled=True
    )
    assert (
        provider.id
        not in get_ai_provider_state(workspace).disabled_instance_provider_ids
    )

    AIProviderHandler.update_feature_setting(
        AI_PROVIDER_FEATURE_KUMA,
        AI_PROVIDER_FEATURE_MODE_MODEL,
        model=model,
    )
    assert (
        get_ai_provider_state(workspace)
        .get_instance_feature_setting(AI_PROVIDER_FEATURE_KUMA)
        .model_id
        == model.id
    )


@pytest.mark.django_db
def test_instance_models_limit_workspace_and_automation_model_settings(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="workspace-model"
    )
    AIProviderModel.objects.create(
        provider_config=provider,
        model_identifier="disabled-model",
        is_enabled=False,
    )
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "workspace-key",
            "models": ["workspace-model", "disabled-model", "workspace-only-model"],
        }
    }
    workspace.save(update_fields=("generative_ai_models_settings",))

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key(workspace) == "workspace-key"
    assert model_type.get_enabled_models(workspace) == ["workspace-model"]
    assert (
        model_type.get_api_key(
            workspace, settings_override={"api_key": "automation-key"}
        )
        == "automation-key"
    )
    assert model_type.get_enabled_models(
        workspace,
        settings_override={
            "models": ["database-model", "disabled-model", "automation-only-model"]
        },
    ) == ["database-model"]


@pytest.mark.django_db
def test_incomplete_legacy_workspace_models_cannot_use_instance_credentials(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {
        "openai": {"models": ["expensive-workspace-model"]}
    }
    workspace.save(update_fields=("generative_ai_models_settings",))
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    AIProviderModel.objects.create(
        provider_config=instance_provider, model_identifier="allowed-instance-model"
    )

    model_type = OpenAIGenerativeAIModelType()

    assert model_type.get_enabled_models(workspace) == ["allowed-instance-model"]
    assert (
        model_type.get_model_settings_override("expensive-workspace-model", workspace)
        is None
    )
    assert model_type.get_model_settings_override(
        "allowed-instance-model", workspace
    ) == {
        "api_key": "instance-key",
        "models": ["allowed-instance-model"],
        "organization": None,
        "base_url": None,
    }


@pytest.mark.django_db
def test_environment_remains_fallback_when_database_provider_is_missing(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]

    model_type = OpenAIGenerativeAIModelType()
    assert model_type.get_api_key() == "environment-key"
    assert model_type.get_enabled_models() == ["environment-model"]


@pytest.mark.django_db
def test_workspace_models_override_matching_instance_models_and_inherit_the_rest(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    AIProviderModel.objects.create(
        provider_config=instance_provider, model_identifier="shared-model"
    )
    AIProviderModel.objects.create(
        provider_config=instance_provider, model_identifier="instance-model"
    )
    workspace_provider = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="openai",
        api_key="workspace-key",
        extra_settings={"organization": "workspace-org"},
    )
    AIProviderModel.objects.create(
        provider_config=workspace_provider, model_identifier="workspace-model"
    )
    AIProviderModel.objects.create(
        provider_config=workspace_provider, model_identifier="shared-model"
    )

    model_type = OpenAIGenerativeAIModelType()

    assert model_type.get_api_key(workspace) == "workspace-key"
    assert model_type.get_enabled_models(workspace) == [
        "workspace-model",
        "shared-model",
        "instance-model",
    ]
    assert model_type.get_organization(workspace) == "workspace-org"
    assert model_type.get_model_settings_override("shared-model", workspace) == {
        "api_key": "workspace-key",
        "models": ["workspace-model", "shared-model"],
        "organization": "workspace-org",
        "base_url": None,
    }
    assert model_type.get_model_settings_override("instance-model", workspace) == {
        "api_key": "instance-key",
        "models": ["shared-model", "instance-model"],
        "organization": None,
        "base_url": None,
    }


@pytest.mark.django_db
def test_disabling_workspace_provider_reveals_inherited_models(data_fixture, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    AIProviderModel.objects.create(
        provider_config=instance_provider, model_identifier="shared-model"
    )
    workspace_provider = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="openai",
        api_key="workspace-key",
        is_active=False,
    )
    AIProviderModel.objects.create(
        provider_config=workspace_provider,
        model_identifier="shared-model",
        is_enabled=False,
    )

    model_type = OpenAIGenerativeAIModelType()

    assert model_type.get_api_key(workspace) == "instance-key"
    assert model_type.get_enabled_models(workspace) == ["shared-model"]
    assert model_type.get_model_settings_override("shared-model", workspace) == {
        "api_key": "instance-key",
        "models": ["shared-model"],
        "organization": None,
        "base_url": None,
    }


@pytest.mark.django_db
def test_disabled_workspace_model_suppresses_matching_inherited_model(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    AIProviderModel.objects.create(
        provider_config=instance_provider, model_identifier="shared-model"
    )
    workspace_provider = AIProviderConfig.objects.create(
        workspace=workspace,
        provider_type="openai",
        api_key="workspace-key",
    )
    AIProviderModel.objects.create(
        provider_config=workspace_provider,
        model_identifier="shared-model",
        is_enabled=False,
    )

    model_type = OpenAIGenerativeAIModelType()

    assert model_type.get_enabled_models(workspace) == []


@pytest.mark.django_db
def test_disabled_inherited_provider_does_not_fall_back_to_environment(
    data_fixture, settings
):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_OPENAI_API_KEY = "environment-key"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    workspace = data_fixture.create_workspace()
    instance_provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="instance-key"
    )
    AIProviderModel.objects.create(
        provider_config=instance_provider, model_identifier="instance-model"
    )
    AIProviderWorkspaceOverride.objects.create(
        workspace=workspace,
        provider_config=instance_provider,
    )

    model_type = OpenAIGenerativeAIModelType()

    assert model_type.get_api_key(workspace) is None
    assert model_type.get_enabled_models(workspace) == []


@pytest.mark.django_db
def test_single_scope_state_is_cached_for_the_local_request(data_fixture, settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    settings.BASEROW_USE_LOCAL_CACHE = True
    workspace = data_fixture.create_workspace()
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )

    with local_cache.context():
        with CaptureQueriesContext(connection) as first_load_queries:
            first_state = get_ai_provider_state(workspace)
        with CaptureQueriesContext(connection) as repeated_load_queries:
            repeated_state = get_ai_provider_state(workspace)

    assert len(first_load_queries) == 4
    assert len(repeated_load_queries) == 0
    assert repeated_state is first_state
