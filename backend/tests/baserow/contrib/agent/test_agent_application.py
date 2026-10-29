from contextlib import nullcontext

from django.urls import reverse
from django.utils import timezone

import pytest

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import AgentApplication
from baserow.core.ai_provider.models import AIProviderConfig, AIProviderModel
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.feature_flags import FF_AGENT_BUILDER
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.last_viewed.handler import LastViewedHandler, LastViewedUpdate
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.storage import get_default_storage
from baserow.core.utils import Progress


def duplicate(data_fixture, user, agent):
    return CoreHandler().duplicate_application(user, agent)


def restore_snapshot(data_fixture, user, agent):
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=agent, name=agent.name, created_by=user
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    return SnapshotHandler().perform_restore(snapshot, Progress(total=100))


def import_workspace_archive(data_fixture, user, agent):
    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    export = handler.export_workspace_applications(
        [agent],
        ImportExportConfig(
            include_permission_data=False, reduce_disk_space_usage=False
        ),
    )
    archive_path = handler.get_export_storage_path(export.get_archive_name())
    with get_default_storage().open(archive_path, "rb") as archive:
        resource = handler.create_resource_from_file(user, "agent.zip", archive)
    workspace = data_fixture.create_workspace(user=user)
    [imported] = handler.import_workspace_applications(user, workspace, resource)
    return imported


@pytest.mark.django_db
@pytest.mark.parametrize("enabled", [True, False])
def test_agent_creation_requires_feature_flag(data_fixture, settings, enabled):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    settings.FEATURE_FLAGS = [FF_AGENT_BUILDER] if enabled else []

    with nullcontext() if enabled else pytest.raises(FeatureDisabledException):
        CoreHandler().create_application(user, workspace, "agent", name="Agent")

    assert list(AgentApplication.objects.values_list("workspace", "name")) == (
        [(workspace.id, "Agent")] if enabled else []
    )


@pytest.mark.django_db
@pytest.mark.parametrize("models_available", [True, False])
def test_new_agent_selects_the_first_enabled_model_and_the_read_tools(
    data_fixture, models_available
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    provider = AIProviderConfig.objects.create(
        workspace=workspace, provider_type="openai", api_key="test-key"
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="disabled", is_enabled=False
    )
    AIProviderModel.objects.create(
        provider_config=provider, model_identifier="ineligible", feature_types=[]
    )
    if models_available:
        AIProviderModel.objects.create(
            provider_config=provider, model_identifier="first-enabled"
        )
        AIProviderModel.objects.create(
            provider_config=provider, model_identifier="second-enabled"
        )

    agent = CoreHandler().create_application(user, workspace, "agent", name="Agent")

    assert (agent.provider_type, agent.model_identifier) == (
        ("openai", "first-enabled") if models_available else (None, None)
    )
    assert agent.instructions == ""
    assert AgentHandler().get_allowed_tool_names(agent) == [
        "list_tables",
        "get_table_schema",
        "list_table_rows",
        "list_views",
    ]


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "configuration", [{}, {"provider_type": None, "model_identifier": None}]
)
@pytest.mark.parametrize(
    "copy_agent,keeps_conversations",
    [(duplicate, True), (restore_snapshot, True), (import_workspace_archive, False)],
)
def test_agent_copy_keeps_configuration_and_only_internal_copies_keep_conversations(
    data_fixture,
    use_tmp_media_root,
    configured_agent,
    copy_agent,
    keeps_conversations,
    configuration,
):
    user = data_fixture.create_user()
    agent = configured_agent(user=user, **configuration)
    data_fixture.create_agent_message(user=user, agent=agent)

    copied = copy_agent(data_fixture, user, agent).specific

    assert isinstance(copied, AgentApplication)
    assert copied.id != agent.id
    assert AgentApplication.objects.filter(id=agent.id).exists()
    assert (copied.instructions, copied.provider_type, copied.model_identifier) == (
        agent.instructions,
        agent.provider_type,
        agent.model_identifier,
    )
    assert copied.conversations.count() == int(keeps_conversations)


@pytest.mark.django_db
@pytest.mark.parametrize("can_read", [True, False])
def test_record_agent_visit_checks_read_permission(
    data_fixture, api_client, api_user, mocker, can_read
):
    agent = data_fixture.create_agent_application(user=api_user if can_read else None)
    loaded = mocker.patch("baserow.contrib.agent.api.views.agent_loaded.send")

    response = api_client.post(reverse("api:agent:item", kwargs={"agent_id": agent.id}))

    assert response.status_code == (204 if can_read else 400)
    if can_read:
        assert response.content == b""
        loaded.assert_called_once_with(
            sender=mocker.ANY, agent_id=agent.id, user=api_user
        )
    else:
        loaded.assert_not_called()


@pytest.mark.django_db
@pytest.mark.workspace_search
def test_workspace_search_finds_agents(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    agent = data_fixture.create_agent_application(user=user, name="Researcher")

    response = api_client.get(
        reverse(
            "api:search:workspace_search",
            kwargs={"workspace_id": agent.workspace_id},
        ),
        {"query": "Research"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200
    [result] = response.json()["results"]
    assert (result["id"], result["type"], result["subtitle"]) == (
        agent.id,
        "agent",
        "Agent",
    )


@pytest.mark.django_db
def test_agent_is_its_own_last_viewed_application(data_fixture):
    user = data_fixture.create_user()
    outsider = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    viewed_at = timezone.now()

    assert (
        LastViewedHandler.mark_viewed(outsider.id, "agent", agent.id, viewed_at) is None
    )
    assert LastViewedHandler.mark_viewed(
        user.id, "agent", agent.id, viewed_at
    ) == LastViewedUpdate(
        application_id=agent.id,
        workspace_id=agent.workspace_id,
        last_viewed=viewed_at,
    )
