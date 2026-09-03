from io import BytesIO

import pytest

from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.handler import CoreHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress


@pytest.mark.django_db
def test_a_database_accepts_an_integration(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    integration = IntegrationService().create_integration(
        user,
        integration_type_registry.get("slack_bot"),
        application=database,
        name="Bot",
        token="xoxb-secret",
    )

    assert integration.application_id == database.id
    assert [i.id for i in database.integrations.all()] == [integration.id]


@pytest.mark.django_db(transaction=True)
def test_an_integration_survives_an_application_export_import(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_integration(
        SlackBotIntegration, application=database, name="Bot", token="xoxb-secret"
    )

    config = ImportExportConfig(
        include_permission_data=False, exclude_sensitive_data=False
    )
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    (integration,) = imported[0].integrations.all()
    assert integration.specific.token == "xoxb-secret"
    assert integration.name == "Bot"


@pytest.mark.django_db(transaction=True)
def test_a_workspace_export_strips_the_token_and_still_imports(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_integration(
        SlackBotIntegration, application=database, name="Bot", token="xoxb-secret"
    )

    config = ImportExportConfig(
        include_permission_data=False, exclude_sensitive_data=True
    )
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)

    assert exported[0]["integrations"][0]["token"] is None

    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    (integration,) = imported[0].integrations.all()
    assert integration.specific.token == ""


@pytest.mark.django_db(transaction=True)
def test_an_export_without_integrations_still_imports(data_fixture):
    """Every export made before integrations were carried lacks the key."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace)

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    exported[0].pop("integrations", None)
    imported, _ = core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    assert imported[0].integrations.count() == 0


@pytest.mark.django_db
def test_an_integration_survives_a_duplicated_application(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_fixture.create_integration(
        SlackBotIntegration, application=database, name="Bot", token="xoxb-secret"
    )

    duplicated = CoreHandler().duplicate_application(user, database)

    (integration,) = duplicated.integrations.all()
    assert integration.specific.token == "xoxb-secret"


@pytest.mark.django_db
def test_an_integration_survives_a_snapshot_and_its_restore(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    data_fixture.create_integration(
        SlackBotIntegration, application=database, name="Bot", token="xoxb-secret"
    )

    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=database, name="snap", created_by=user
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100))

    (integration,) = restored.integrations.all()
    assert integration.specific.token == "xoxb-secret"


@pytest.mark.django_db
def test_a_database_refuses_an_integration_carrying_a_user(data_fixture):
    """
    A button runs as whoever clicked, never as an integration's
    `authorized_user` (ADR 006 section 5). Refusing the action the id is
    attached to is not enough: the integration must not exist on a database
    at all, or it rides along in every duplicate and snapshot.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)

    with pytest.raises(ApplicationOperationNotSupported):
        IntegrationService().create_integration(
            user,
            integration_type_registry.get("local_baserow"),
            application=database,
            name="Local Baserow",
        )

    assert database.integrations.count() == 0


@pytest.mark.django_db
def test_a_database_accepts_what_its_actions_can_carry(data_fixture):
    """The two lists are one, so they cannot drift apart."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    application_type = application_type_registry.get("database")

    carried_by_an_action = {
        allowed
        for action_type in database_workflow_action_type_registry.get_all()
        for allowed in action_type.allowed_integration_types
    }
    assert "slack_bot" in carried_by_an_action

    for integration_type in integration_type_registry.get_all():
        accepted = application_type.supports_integration_type(integration_type)
        assert accepted == (integration_type.type in carried_by_an_action), (
            f"{integration_type.type} is accepted by the database but no "
            f"action can carry it"
        )
