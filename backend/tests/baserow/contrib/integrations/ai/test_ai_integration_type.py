import json

import pytest

from baserow.contrib.integrations.ai.integration_types import AIIntegrationType
from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_ai_integration_creation(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
    )

    assert integration.ai_settings == {}
    assert integration.application_id == application.id
    assert isinstance(integration, AIIntegration)


@pytest.mark.django_db
def test_ai_integration_creation_with_settings(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    ai_settings = {
        "openai": {
            "api_key": "sk-test123",
            "models": ["gpt-4", "gpt-3.5-turbo"],
            "organization": "org-123",
        }
    }

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings=ai_settings,
    )

    assert integration.ai_settings == ai_settings
    assert integration.application_id == application.id


@pytest.mark.django_db
def test_ai_integration_update(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={"openai": {"api_key": "sk-old", "models": ["gpt-3.5-turbo"]}},
    )

    updated_integration = IntegrationService().update_integration(
        user,
        integration,
        ai_settings={
            "openai": {"api_key": "sk-new", "models": ["gpt-4"]},
            "anthropic": {"api_key": "sk-anthropic", "models": ["claude-3-opus"]},
        },
    )

    assert updated_integration.ai_settings["openai"]["api_key"] == "sk-new"
    assert updated_integration.ai_settings["openai"]["models"] == ["gpt-4"]
    assert updated_integration.ai_settings["anthropic"]["api_key"] == "sk-anthropic"
    assert updated_integration.ai_settings["anthropic"]["models"] == ["claude-3-opus"]


@pytest.mark.django_db
def test_ai_integration_partial_update(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    original_settings = {
        "openai": {"api_key": "sk-original", "models": ["gpt-4"]},
        "anthropic": {"api_key": "sk-anthropic", "models": ["claude-3-opus"]},
    }

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings=original_settings,
    )

    updated_integration = IntegrationService().update_integration(
        user,
        integration,
        ai_settings={"openai": {"api_key": "sk-updated", "models": ["gpt-4-turbo"]}},
    )

    # OpenAI should be updated
    assert updated_integration.ai_settings["openai"]["api_key"] == "sk-updated"
    assert updated_integration.ai_settings["openai"]["models"] == ["gpt-4-turbo"]
    # Anthropic should be removed (replaced, not merged)
    assert "anthropic" not in updated_integration.ai_settings


@pytest.mark.django_db
def test_ai_integration_serializer_field_names(data_fixture):
    integration_type = AIIntegrationType()

    expected_fields = ["ai_settings"]
    assert integration_type.serializer_field_names == expected_fields
    assert integration_type.allowed_fields == expected_fields
    assert integration_type.request_serializer_field_names == expected_fields


@pytest.mark.django_db
def test_ai_integration_serialized_dict_type(data_fixture):
    integration_type = AIIntegrationType()

    serialized_dict_class = integration_type.SerializedDict
    annotations = getattr(serialized_dict_class, "__annotations__", {})

    assert "ai_settings" in annotations


@pytest.mark.django_db
def test_ai_integration_export_serialized(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={
            "openai": {
                "api_key": "sk-secret123",
                "models": ["gpt-4"],
                "organization": "org-123",
            }
        },
    )

    serialized = json.loads(json.dumps(integration_type.export_serialized(integration)))

    expected_serialized = {
        "id": AnyInt(),
        "type": "ai",
        "ai_settings": {
            "openai": {
                "api_key": "sk-secret123",
                "models": ["gpt-4"],
                "organization": "org-123",
            }
        },
        "name": "",
        "order": "1.00000000000000000000",
    }

    assert serialized == expected_serialized


@pytest.mark.django_db
def test_ai_integration_export_serialized_exclude_sensitive(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={
            "openai": {
                "api_key": "sk-secret123",
                "models": ["gpt-4"],
            }
        },
    )

    serialized = json.loads(
        json.dumps(
            integration_type.export_serialized(
                integration,
                import_export_config=ImportExportConfig(
                    include_permission_data=False,
                    reduce_disk_space_usage=False,
                    exclude_sensitive_data=True,
                ),
            )
        )
    )

    expected_serialized = {
        "id": AnyInt(),
        "type": "ai",
        "ai_settings": None,
        "name": "",
        "order": "1.00000000000000000000",
    }

    assert serialized == expected_serialized


@pytest.mark.django_db
def test_ai_integration_import_serialized(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()

    serialized_data = {
        "id": 1,
        "type": "ai",
        "ai_settings": {},  # Empty on import (will inherit from workspace)
    }

    imported_integration = integration_type.import_serialized(
        application, serialized_data, {}, lambda x, d: x
    )

    assert imported_integration.ai_settings == {}
    assert imported_integration.application_id == application.id


@pytest.mark.django_db
def test_ai_integration_deletion(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = integration_type_registry.get("ai")

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={"openai": {"api_key": "sk-test", "models": ["gpt-4"]}},
    )

    integration_id = integration.id

    IntegrationService().delete_integration(user, integration)

    # Verify integration is deleted
    assert not AIIntegration.objects.filter(id=integration_id).exists()


@pytest.mark.django_db
def test_ai_integration_get_provider_settings_from_workspace(data_fixture, settings):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(
        user=user, workspace=workspace
    )

    workspace.generative_ai_models_settings = {
        "openai": {"api_key": "sk-workspace-key", "models": ["gpt-3.5-turbo"]}
    }
    workspace.save()

    integration_type = AIIntegrationType()

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={},
    )

    # Should get settings from workspace
    provider_settings = integration_type.get_provider_settings(integration, "openai")
    assert provider_settings["api_key"] == "sk-workspace-key"


@pytest.mark.django_db
def test_ai_integration_get_provider_settings_empty(data_fixture, settings):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    settings.BASEROW_OPENAI_API_KEY = "sk-env-key"

    integration_type = AIIntegrationType()

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={},
    )

    # Should return empty dict when no integration or workspace settings exist
    provider_settings = integration_type.get_provider_settings(integration, "openai")
    assert provider_settings == {}


@pytest.mark.django_db
def test_ai_integration_get_provider_settings(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={
            "openai": {
                "api_key": "sk-test",
                "models": ["gpt-4"],
                "organization": "org-123",
            }
        },
    )

    settings = integration_type.get_provider_settings(integration, "openai")
    assert settings == {
        "api_key": "sk-test",
        "models": ["gpt-4"],
        "organization": "org-123",
    }


@pytest.mark.django_db
def test_ai_integration_is_provider_overridden(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    integration_type = AIIntegrationType()

    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={"openai": {"api_key": "sk-test", "models": ["gpt-4"]}},
    )

    assert integration_type.is_provider_overridden(integration, "openai") is True
    assert integration_type.is_provider_overridden(integration, "anthropic") is False


@pytest.mark.django_db
def test_ai_integration_settings_hierarchy(data_fixture, settings):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(
        user=user, workspace=workspace
    )

    settings.BASEROW_OPENAI_API_KEY = "sk-env-key"
    settings.BASEROW_OPENAI_MODELS = ["gpt-3.5-turbo"]

    workspace.generative_ai_models_settings = {
        "openai": {"api_key": "sk-workspace-key", "models": ["gpt-4"]}
    }
    workspace.save()

    integration_type = AIIntegrationType()
    integration = IntegrationService().create_integration(
        user,
        integration_type,
        application=application,
        ai_settings={"openai": {"api_key": "sk-integration-key", "models": ["gpt-4o"]}},
    )

    # Integration settings should take precedence
    provider_settings = integration_type.get_provider_settings(integration, "openai")
    assert provider_settings["api_key"] == "sk-integration-key"
    assert provider_settings["models"] == ["gpt-4o"]

    # Now update integration to remove OpenAI override
    IntegrationService().update_integration(user, integration, ai_settings={})
    integration.refresh_from_db()

    # Should now get workspace settings
    provider_settings = integration_type.get_provider_settings(integration, "openai")
    assert provider_settings["api_key"] == "sk-workspace-key"
    assert provider_settings["models"] == ["gpt-4"]
