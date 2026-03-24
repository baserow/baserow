"""
Tests that verify the data migration logic for populating AIProviderConfig
from env vars, workspace JSONField settings, AI integrations, AI field FK
backfill, AI agent service FK backfill, and assistant default model.

These tests exercise the same logic as migration 0115_populate_ai_providers
but in a unit-testable way, without running the actual migration.
"""

import os
from unittest.mock import patch

import pytest

from baserow.core.ai_provider.models import (
    AIFeatureDefaultModel,
    AIProviderConfig,
    AIProviderModel,
)


class _FakeApps:
    """Shim so the migration functions resolve real models."""

    def get_model(self, app_label, model_name):
        from django.apps import apps as real_apps

        return real_apps.get_model(app_label, model_name)


def _get_migration_module():
    import importlib

    return importlib.import_module("baserow.core.migrations.0115_populate_ai_providers")


_apps = _FakeApps()


def _run_env_var_migration():
    _get_migration_module().populate_from_env_vars(_apps, None)


def _run_workspace_migration():
    _get_migration_module().populate_from_workspace_settings(_apps, None)


def _run_ai_integration_migration():
    _get_migration_module().populate_from_ai_integrations(_apps, None)


def _run_ai_field_backfill():
    _get_migration_module().backfill_ai_field_fk(_apps, None)


def _run_ai_agent_service_backfill():
    _get_migration_module().backfill_ai_agent_service_fk(_apps, None)


def _run_assistant_default_model():
    _get_migration_module().populate_assistant_default_model(_apps, None)


@pytest.mark.django_db
def test_env_var_migration_creates_openai_provider():
    env = {
        "BASEROW_OPENAI_API_KEY": "sk-test-openai",
        "BASEROW_OPENAI_MODELS": "gpt-4o,gpt-4o-mini",
        "BASEROW_OPENAI_ORGANIZATION": "org-test",
    }
    with patch.dict(os.environ, env, clear=False):
        _run_env_var_migration()

    configs = AIProviderConfig.objects.filter(
        provider_type="openai",
        scope_content_type__isnull=True,
    )
    assert configs.count() == 1
    config = configs.first()
    assert config.name == "OpenAI"
    assert config.api_key == "sk-test-openai"
    assert config.extra_settings.get("organization") == "org-test"
    assert config.is_active

    models = list(config.models.order_by("id"))
    assert len(models) == 2
    assert models[0].model_identifier == "gpt-4o"
    assert models[1].model_identifier == "gpt-4o-mini"

    # Each model should have all features enabled
    for model in models:
        features = set(model.features.values_list("feature_type", flat=True))
        assert "ai_field" in features
        assert "ai_assistant" in features


@pytest.mark.django_db
def test_env_var_migration_creates_ollama_provider():
    env = {
        "BASEROW_OLLAMA_HOST": "http://localhost:11434",
        "BASEROW_OLLAMA_MODELS": "llama3,mistral",
    }
    with patch.dict(os.environ, env, clear=False):
        _run_env_var_migration()

    configs = AIProviderConfig.objects.filter(
        provider_type="ollama",
        scope_content_type__isnull=True,
    )
    assert configs.count() == 1
    config = configs.first()
    assert config.name == "Ollama"
    assert config.api_key == ""  # Ollama has no API key
    assert config.extra_settings.get("host") == "http://localhost:11434"

    models = list(config.models.order_by("id"))
    assert len(models) == 2
    assert models[0].model_identifier == "llama3"


@pytest.mark.django_db
def test_env_var_migration_skips_unconfigured_providers():
    # No env vars set for any provider
    with patch.dict(os.environ, {}, clear=False):
        # Clear any existing AI-related env vars
        for key in list(os.environ.keys()):
            if key.startswith("BASEROW_") and (
                "API_KEY" in key or "MODELS" in key or "HOST" in key
            ):
                os.environ.pop(key, None)
        _run_env_var_migration()

    assert (
        AIProviderConfig.objects.filter(
            scope_content_type__isnull=True,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_env_var_migration_is_idempotent():
    env = {
        "BASEROW_OPENAI_API_KEY": "sk-test",
        "BASEROW_OPENAI_MODELS": "gpt-4o",
    }
    with patch.dict(os.environ, env, clear=False):
        _run_env_var_migration()
        _run_env_var_migration()  # Run again

    # Should still only have one provider
    assert (
        AIProviderConfig.objects.filter(
            provider_type="openai",
            scope_content_type__isnull=True,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_workspace_settings_migration(data_fixture):
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "sk-ws-openai",
            "models": ["gpt-4o", "gpt-4o-mini"],
            "organization": "org-ws",
        },
        "anthropic": {
            "api_key": "sk-ant-ws",
            "models": ["claude-sonnet-4-20250514"],
        },
    }
    workspace.save()

    _run_workspace_migration()

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.models import Workspace

    ws_ct = ContentType.objects.get_for_model(Workspace)

    # Two providers created at workspace scope
    ws_configs = AIProviderConfig.objects.filter(
        scope_content_type=ws_ct,
        scope_object_id=workspace.id,
    )
    assert ws_configs.count() == 2

    openai_config = ws_configs.get(provider_type="openai")
    assert openai_config.api_key == "sk-ws-openai"
    assert openai_config.extra_settings.get("organization") == "org-ws"
    assert openai_config.models.count() == 2

    anthropic_config = ws_configs.get(provider_type="anthropic")
    assert anthropic_config.api_key == "sk-ant-ws"
    assert anthropic_config.models.count() == 1
    assert (
        anthropic_config.models.first().model_identifier == "claude-sonnet-4-20250514"
    )


@pytest.mark.django_db
def test_workspace_settings_migration_is_idempotent(data_fixture):
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {
        "openai": {
            "api_key": "sk-ws",
            "models": ["gpt-4o"],
        },
    }
    workspace.save()

    _run_workspace_migration()
    _run_workspace_migration()  # Run again

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.models import Workspace

    ws_ct = ContentType.objects.get_for_model(Workspace)
    assert (
        AIProviderConfig.objects.filter(
            scope_content_type=ws_ct,
            scope_object_id=workspace.id,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_workspace_settings_migration_skips_empty(data_fixture):
    workspace = data_fixture.create_workspace()
    workspace.generative_ai_models_settings = {}
    workspace.save()

    _run_workspace_migration()

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.models import Workspace

    ws_ct = ContentType.objects.get_for_model(Workspace)
    assert (
        AIProviderConfig.objects.filter(
            scope_content_type=ws_ct,
            scope_object_id=workspace.id,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_workspace_settings_migration_multiple_workspaces(data_fixture):
    ws1 = data_fixture.create_workspace()
    ws1.generative_ai_models_settings = {
        "openai": {"api_key": "sk-1", "models": ["gpt-4o"]},
    }
    ws1.save()

    ws2 = data_fixture.create_workspace()
    ws2.generative_ai_models_settings = {
        "anthropic": {"api_key": "sk-2", "models": ["claude-sonnet-4-20250514"]},
    }
    ws2.save()

    _run_workspace_migration()

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.models import Workspace

    ws_ct = ContentType.objects.get_for_model(Workspace)

    ws1_configs = AIProviderConfig.objects.filter(
        scope_content_type=ws_ct, scope_object_id=ws1.id
    )
    assert ws1_configs.count() == 1
    assert ws1_configs.first().provider_type == "openai"

    ws2_configs = AIProviderConfig.objects.filter(
        scope_content_type=ws_ct, scope_object_id=ws2.id
    )
    assert ws2_configs.count() == 1
    assert ws2_configs.first().provider_type == "anthropic"


# ── AI Integration (Builder) migration ──────────────────────────────


@pytest.mark.django_db
def test_ai_integration_migration(data_fixture):
    """AIIntegration.ai_settings → application-level AIProviderConfig."""

    from baserow.contrib.integrations.ai.models import AIIntegration

    workspace = data_fixture.create_workspace()
    app = data_fixture.create_builder_application(workspace=workspace)
    integration = AIIntegration.objects.create(
        application=app,
        ai_settings={
            "openai": {
                "api_key": "sk-builder-openai",
                "models": ["gpt-4o"],
                "organization": "org-builder",
            },
        },
    )

    _run_ai_integration_migration()

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.models import Application

    app_ct = ContentType.objects.get_for_model(Application)
    configs = AIProviderConfig.objects.filter(
        scope_content_type=app_ct, scope_object_id=app.id
    )
    assert configs.count() == 1
    config = configs.first()
    assert config.provider_type == "openai"
    assert config.api_key == "sk-builder-openai"
    assert config.extra_settings.get("organization") == "org-builder"
    assert config.models.count() == 1
    assert config.models.first().model_identifier == "gpt-4o"


@pytest.mark.django_db
def test_ai_integration_migration_skips_empty(data_fixture):
    from baserow.contrib.integrations.ai.models import AIIntegration

    workspace = data_fixture.create_workspace()
    app = data_fixture.create_builder_application(workspace=workspace)
    AIIntegration.objects.create(application=app, ai_settings={})

    _run_ai_integration_migration()

    from django.contrib.contenttypes.models import ContentType

    from baserow.core.models import Application

    app_ct = ContentType.objects.get_for_model(Application)
    assert (
        AIProviderConfig.objects.filter(
            scope_content_type=app_ct, scope_object_id=app.id
        ).count()
        == 0
    )


# ── AIField FK backfill ─────────────────────────────────────────────


@pytest.mark.django_db
def test_ai_field_fk_backfill(data_fixture):
    """AIField.ai_generative_ai_type/model → ai_provider_model FK."""

    from baserow.core.ai_provider.handler import AIProviderHandler

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    # Create a provider at workspace scope with a matching model
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type="workspace",
        scope_id=workspace.id,
        api_key="sk-test",
        models_data=[{"model_identifier": "gpt-4o", "features": ["ai_field"]}],
    )

    from baserow_premium.fields.models import AIField

    field = AIField.objects.create(
        table=table,
        order=1,
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4o",
        ai_provider_model=None,
    )

    _run_ai_field_backfill()

    field.refresh_from_db()
    assert field.ai_provider_model is not None
    assert field.ai_provider_model.model_identifier == "gpt-4o"
    assert field.ai_provider_model.provider_config.id == provider.id


@pytest.mark.django_db
def test_ai_field_fk_backfill_skips_already_set(data_fixture):
    """Fields with ai_provider_model already set are not overwritten."""

    from baserow.core.ai_provider.handler import AIProviderHandler

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type="workspace",
        scope_id=workspace.id,
        api_key="sk-test",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_field"]},
            {"model_identifier": "gpt-4o-mini", "features": ["ai_field"]},
        ],
    )
    gpt4o = provider.models.get(model_identifier="gpt-4o")

    from baserow_premium.fields.models import AIField

    field = AIField.objects.create(
        table=table,
        order=1,
        name="AI",
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4o-mini",
        ai_provider_model=gpt4o,  # Already set to a different model
    )

    _run_ai_field_backfill()

    field.refresh_from_db()
    # Should NOT have changed to gpt-4o-mini — keeps the existing FK
    assert field.ai_provider_model.model_identifier == "gpt-4o"


@pytest.mark.django_db
def test_ai_field_fk_backfill_falls_back_to_instance(data_fixture):
    """Falls back to instance-level provider when no workspace provider matches."""

    from baserow.core.ai_provider.handler import AIProviderHandler

    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    # Create provider at instance scope only
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="anthropic",
        name="Anthropic",
        scope_type="instance",
        api_key="sk-ant",
        models_data=[
            {"model_identifier": "claude-sonnet-4-20250514", "features": ["ai_field"]}
        ],
    )

    from baserow_premium.fields.models import AIField

    field = AIField.objects.create(
        table=table,
        order=1,
        name="AI",
        ai_generative_ai_type="anthropic",
        ai_generative_ai_model="claude-sonnet-4-20250514",
        ai_provider_model=None,
    )

    _run_ai_field_backfill()

    field.refresh_from_db()
    assert field.ai_provider_model is not None
    assert field.ai_provider_model.model_identifier == "claude-sonnet-4-20250514"


# ── AIAgentService FK backfill ──────────────────────────────────────


@pytest.mark.django_db
def test_ai_agent_service_fk_backfill(data_fixture):
    """AIAgentService.ai_generative_ai_type/model → ai_provider_model FK."""

    from baserow.contrib.integrations.ai.models import (
        AIAgentService,
        AIIntegration,
    )
    from baserow.core.ai_provider.handler import AIProviderHandler

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    app = data_fixture.create_builder_application(workspace=workspace)
    integration = AIIntegration.objects.create(application=app)

    # Create a provider at workspace scope
    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type="workspace",
        scope_id=workspace.id,
        api_key="sk-test",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_agent_node"]}
        ],
    )

    service = AIAgentService.objects.create(
        integration=integration,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="gpt-4o",
        ai_provider_model=None,
    )

    _run_ai_agent_service_backfill()

    service.refresh_from_db()
    assert service.ai_provider_model is not None
    assert service.ai_provider_model.model_identifier == "gpt-4o"


# ── Assistant default model ─────────────────────────────────────────


@pytest.mark.django_db
def test_assistant_default_model_from_env_var():
    """BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL → AIFeatureDefaultModel."""

    from baserow.core.ai_provider.handler import AIProviderHandler

    # First create an instance-level provider with the model
    user_model = None  # migration doesn't need a user
    AIProviderConfig.objects.filter(scope_content_type__isnull=True).delete()

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="test@test.com", email="test@test.com", password="test"
    )

    provider = AIProviderHandler.create_provider(
        user=user,
        provider_type="openai",
        name="OpenAI",
        scope_type="instance",
        api_key="sk-test",
        models_data=[
            {"model_identifier": "gpt-4o", "features": ["ai_assistant"]}
        ],
    )

    env = {"BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL": "openai/gpt-4o"}
    with patch.dict(os.environ, env, clear=False):
        _run_assistant_default_model()

    default = AIFeatureDefaultModel.objects.filter(
        feature_type="ai_assistant",
        scope_content_type__isnull=True,
    ).first()
    assert default is not None
    assert default.provider_model.model_identifier == "gpt-4o"


@pytest.mark.django_db
def test_assistant_default_model_groq_format():
    """Handles groq:openai/gpt-oss-120b format correctly."""

    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="test2@test.com", email="test2@test.com", password="test"
    )

    from baserow.core.ai_provider.handler import AIProviderHandler

    AIProviderHandler.create_provider(
        user=user,
        provider_type="groq",
        name="Groq",
        scope_type="instance",
        api_key="gsk-test",
        models_data=[
            {"model_identifier": "gpt-oss-120b", "features": ["ai_assistant"]}
        ],
    )

    env = {"BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL": "groq:openai/gpt-oss-120b"}
    with patch.dict(os.environ, env, clear=False):
        _run_assistant_default_model()

    default = AIFeatureDefaultModel.objects.filter(
        feature_type="ai_assistant",
        scope_content_type__isnull=True,
    ).first()
    assert default is not None
    assert default.provider_model.model_identifier == "gpt-oss-120b"


@pytest.mark.django_db
def test_assistant_default_model_skips_when_no_env_var():
    """No default created when env var is not set."""

    env = {"BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL": ""}
    with patch.dict(os.environ, env, clear=False):
        _run_assistant_default_model()

    assert AIFeatureDefaultModel.objects.filter(feature_type="ai_assistant").count() == 0
