import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.integrations.ai.models import AIIntegration
from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.ai_provider.models import AIProviderFeatureSetting


@pytest.mark.django_db
def test_audit_is_read_only_and_omits_secrets(data_fixture, settings):
    settings.BASEROW_OPENAI_API_KEY = "environment-secret"
    settings.BASEROW_OPENAI_MODELS = ["environment-model"]
    workspace = data_fixture.create_workspace(
        name="private-workspace-name",
        generative_ai_models_settings={
            "openai": {"api_key": "workspace-secret", "models": ["legacy-model"]},
            "private-malformed-key": {"api_key": "secret"},
        },
    )
    provider = AIProviderHandler.create_provider(
        provider_type="openai",
        api_key="database-secret",
        extra_settings={"base_url": "https://private-endpoint.example"},
        models_data=[{"model_identifier": "database-model"}],
    )
    integration = data_fixture.create_integration(
        AIIntegration,
        application=data_fixture.create_builder_application(workspace=workspace),
        ai_settings={
            "openai": {"api_key": "integration-secret"},
            "https://private-url-key.example": {"api_key": "secret"},
        },
    )
    service = data_fixture.create_ai_agent_service(
        integration=integration,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="database-model",
        ai_prompt="'private-prompt'",
    )

    output = StringIO()
    with (
        CaptureQueriesContext(connection) as queries,
        patch(
            "baserow.core.generative_ai.generative_ai_model_types.OpenAIGenerativeAIModelType.prompt"
        ) as prompt,
    ):
        call_command("audit_ai_provider_settings", stdout=output)

    report = json.loads(output.getvalue())
    assert report["verification"] == "manual_rehearsal_required"
    assert "openai" in report["environment_provider_types"]
    assert report["providers"][0]["id"] == provider.id
    assert report["providers"][0]["models"][0]["identifier"] == "database-model"
    assert report["workspaces"] == [
        {
            "id": workspace.id,
            "trashed": False,
            "legacy_settings": {
                "provider_types": ["openai"],
                "unknown_provider_count": 1,
                "malformed": False,
            },
        }
    ]
    assert report["ai_integrations"][0]["settings_provenance"] == "unknown"
    assert report["ai_integrations"][0]["override_settings"] == {
        "provider_types": ["openai"],
        "unknown_provider_count": 1,
        "malformed": False,
    }
    assert report["ai_agents"][0]["id"] == service.id
    for secret in (
        "environment-secret",
        "workspace-secret",
        "database-secret",
        "integration-secret",
        "private-endpoint",
        "private-prompt",
        "private-workspace-name",
        "private-malformed-key",
        "private-url-key",
    ):
        assert secret not in output.getvalue()
    assert all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries)
    prompt.assert_not_called()


@pytest.mark.django_db
def test_audit_workspace_filter_includes_both_publication_types(data_fixture):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(workspace=workspace)
    published_builder = data_fixture.create_builder_application(workspace=None)
    domain = data_fixture.create_builder_sub_domain(
        builder=builder, published_to=published_builder
    )
    automation = data_fixture.create_automation_application(workspace=workspace)
    original = data_fixture.create_automation_workflow(automation=automation)
    published_automation = data_fixture.create_automation_application(
        workspace=None, published_from=original
    )
    published_workflow = data_fixture.create_automation_workflow(
        automation=published_automation
    )
    expected_integrations = []
    for application in (builder, published_builder, automation, published_automation):
        integration = data_fixture.create_integration(
            AIIntegration, application=application, ai_settings={}
        )
        expected_integrations.append(integration.id)
        data_fixture.create_ai_agent_service(integration=integration)
    excluded = data_fixture.create_integration(AIIntegration)
    data_fixture.create_ai_agent_service(integration=excluded)
    instance_provider = AIProviderHandler.create_provider(
        provider_type="openai", api_key="instance-key"
    )
    AIProviderHandler.create_provider(
        provider_type="openai",
        api_key="other-key",
        workspace=excluded.application.workspace,
    )

    output = StringIO()
    call_command("audit_ai_provider_settings", workspace_id=workspace.id, stdout=output)
    report = json.loads(output.getvalue())
    assert [row["id"] for row in report["ai_integrations"]] == expected_integrations
    assert {row["integration_id"] for row in report["ai_agents"]} == set(
        expected_integrations
    )
    assert {row["workspace_id"] for row in report["ai_integrations"]} == {workspace.id}
    assert report["ai_integrations"][1]["publication"] == {
        "type": "builder",
        "domain_id": domain.id,
    }
    assert report["ai_integrations"][3]["publication"] == {
        "type": "automation",
        "source_workflow_id": original.id,
        "workflows": [{"id": published_workflow.id, "state": published_workflow.state}],
    }
    assert [row["id"] for row in report["providers"]] == [instance_provider.id]
    assert all(
        row["settings_provenance"] == "inherit" for row in report["ai_integrations"]
    )


@pytest.mark.django_db
def test_audit_keeps_trash_unknown_settings_and_unbound_services(data_fixture):
    workspace = data_fixture.create_workspace(generative_ai_models_settings=["invalid"])
    integration = data_fixture.create_integration(
        AIIntegration,
        application=data_fixture.create_builder_application(workspace=workspace),
        ai_settings=["private-invalid-value"],
        trashed=True,
    )
    unbound = data_fixture.create_ai_agent_service(integration=None)
    AIProviderFeatureSetting.objects.create(
        workspace=workspace, feature_type="kuma", is_enabled=False
    )
    output = StringIO()
    call_command("audit_ai_provider_settings", stdout=output)
    report = json.loads(output.getvalue())
    assert report["workspaces"][0]["legacy_settings"]["malformed"] is True
    row = report["ai_integrations"][0]
    assert row["id"] == integration.id
    assert row["trashed"] is True
    assert row["override_settings"]["malformed"] is True
    assert row["settings_provenance"] == "unknown"
    assert "private-invalid-value" not in output.getvalue()
    assert {row["id"] for row in report["ai_agents"]} == {unbound.id}
    assert report["feature_settings"] == [
        {
            "workspace_id": workspace.id,
            "feature_type": "kuma",
            "model_id": None,
            "is_enabled": False,
        }
    ]


@pytest.mark.django_db
def test_audit_rejects_unknown_workspace():
    output = StringIO()
    with pytest.raises(CommandError, match="workspace does not exist"):
        call_command("audit_ai_provider_settings", workspace_id=-1, stdout=output)
    assert output.getvalue() == ""


@pytest.mark.django_db
def test_audit_does_not_guess_an_unlinked_publications_workspace(data_fixture):
    workspace = data_fixture.create_workspace()
    integration = data_fixture.create_integration(
        AIIntegration,
        application=data_fixture.create_builder_application(workspace=None),
        ai_settings={"openai": {"api_key": "old-snapshot-key"}},
    )
    output = StringIO()
    call_command("audit_ai_provider_settings", stdout=output)
    report = json.loads(output.getvalue())
    assert len(report["ai_integrations"]) == 1
    row = report["ai_integrations"][0]
    assert row["id"] == integration.id
    assert row["workspace_id"] is None
    assert row["publication"] is None
    assert row["settings_provenance"] == "unknown"
    scoped_output = StringIO()
    call_command(
        "audit_ai_provider_settings", workspace_id=workspace.id, stdout=scoped_output
    )
    assert json.loads(scoped_output.getvalue())["ai_integrations"] == []
