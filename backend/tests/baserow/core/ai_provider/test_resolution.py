from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.ai_provider.models import (
    AIProviderConfig,
    AIProviderModel,
    AIProviderWorkspaceOverride,
)
from baserow.core.cache import local_cache
from baserow.core.generative_ai.generative_ai_model_types import (
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
def test_database_provider_resolution_is_cached_per_request(settings):
    settings.FEATURE_FLAGS = ["ai-providers"]
    provider = AIProviderConfig.objects.create(
        provider_type="openai", api_key="database-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="database-model"
    )
    model_type = OpenAIGenerativeAIModelType()

    with local_cache.context(), CaptureQueriesContext(connection) as queries:
        assert model_type.get_api_key() == "database-key"
        assert model_type.get_enabled_models() == ["database-model"]
        assert model_type.get_api_key() == "database-key"

    assert len(queries) == 2


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
