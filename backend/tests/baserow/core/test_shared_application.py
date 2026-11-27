from io import BytesIO
from time import monotonic
from unittest.mock import patch

from django.db import connection, transaction

import pytest

from baserow.contrib.database.models import Database
from baserow.contrib.integrations.mcp.integration_types import (
    MCPServerIntegrationType,
)
from baserow.contrib.integrations.oauth_account.integration_types import (
    OAuthAccountIntegrationTypeMixin,
)
from baserow.core.application_types import SharedApplicationType
from baserow.core.exceptions import ApplicationOperationNotSupported, PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.models import (
    SHARED_APPLICATION_NAME,
    Application,
    SharedApplication,
    Workspace,
)
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.tasks import (
    CREATE_MISSING_SHARED_APPLICATIONS_TIME_LIMIT,
    create_missing_shared_applications_task,
)
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import visible_applications
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_templates.exceptions import TemplateHasNoContent
from baserow.core.user_templates.handler import UserTemplateHandler


def ids(applications):
    return [application.id for application in applications]


@pytest.mark.django_db
def test_shared_application_is_returned_by_the_default_managers(data_fixture):
    workspace = data_fixture.create_workspace()
    shared_application = data_fixture.create_shared_application(workspace=workspace)

    assert ids(Application.objects.filter(workspace=workspace)) == [
        shared_application.id
    ]
    assert ids(workspace.application_set.all()) == [shared_application.id]
    assert ids(CoreHandler().list_applications_in_workspace(workspace)) == [
        shared_application.id
    ]

    application = CoreHandler().get_application(shared_application.id)
    assert isinstance(application.specific, SharedApplication)
    assert application.get_type().type == SharedApplicationType.type


@pytest.mark.django_db
def test_objects_without_shared_leave_the_shared_application_out(data_fixture):
    workspace = data_fixture.create_workspace()
    data_fixture.create_shared_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    trashed_database = data_fixture.create_database_application(
        workspace=workspace, order=2, trashed=True
    )

    # Related managers like `workspace.application_set` keep the shared application.
    for model in [Application, Database, SharedApplication]:
        assert model._default_manager.name == "objects"

    assert ids(Application.objects_without_shared.all()) == [database.id]
    assert ids(workspace.application_set_without_shared()) == [database.id]
    assert ids(workspace.application_set_without_shared(include_trash=True)) == [
        database.id,
        trashed_database.id,
    ]


def test_shared_application_type_supports_the_integration_types_of_a_workspace():
    shared_application_type = application_type_registry.get(SharedApplicationType.type)

    assert not shared_application_type.supports_user_sources
    assert not shared_application_type.supports_snapshots
    assert not shared_application_type.is_user_managed
    for integration_type in integration_type_registry.get_all():
        # Only the agent that owns an MCP server reads it, and an account signed in
        # through OAuth stays with the application it was connected on.
        assert shared_application_type.supports_integration_type(integration_type) == (
            integration_type.type != MCPServerIntegrationType.type
            and not isinstance(integration_type, OAuthAccountIntegrationTypeMixin)
        )


@pytest.mark.django_db
def test_shared_application_cannot_be_created_exported_or_imported(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    shared_application_type = application_type_registry.get(SharedApplicationType.type)
    config = ImportExportConfig(include_permission_data=False)

    with pytest.raises(ApplicationOperationNotSupported):
        CoreHandler().create_application(
            user, workspace, SharedApplicationType.type, name="Shared"
        )
    with pytest.raises(ApplicationOperationNotSupported):
        shared_application_type.export_serialized(shared_application, config)
    with pytest.raises(ApplicationOperationNotSupported):
        shared_application_type.import_serialized(
            workspace,
            {"id": shared_application.id, "type": "shared", "name": "S", "order": 0},
            config,
            {},
        )

    assert ids(SharedApplication.objects.all()) == [shared_application.id]


@pytest.mark.django_db
def test_shared_application_cannot_be_updated_duplicated_deleted_or_snapshotted(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    handler = CoreHandler()

    with pytest.raises(ApplicationOperationNotSupported):
        handler.update_application(user, shared_application, name="Renamed")
    with pytest.raises(ApplicationOperationNotSupported):
        handler.duplicate_application(user, shared_application)
    with pytest.raises(ApplicationOperationNotSupported):
        handler.delete_application(user, shared_application)
    with pytest.raises(ApplicationOperationNotSupported):
        SnapshotHandler().create(shared_application.id, user, "Snapshot")

    shared_application.refresh_from_db()
    assert shared_application.name == "__shared__"
    assert not shared_application.trashed
    assert ids(Application.objects_and_trash.filter(workspace=workspace)) == [
        shared_application.id
    ]


@pytest.mark.django_db(transaction=True)
def test_workspace_export_leaves_the_shared_application_out(data_fixture):
    workspace = data_fixture.create_workspace()
    data_fixture.create_shared_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    config = ImportExportConfig(include_permission_data=False)

    exported = CoreHandler().export_workspace_applications(workspace, BytesIO(), config)

    assert [application["id"] for application in exported] == [database.id]


@pytest.mark.django_db
def test_export_job_and_user_templates_leave_the_shared_application_out(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    export_job_type = ExportApplicationsJobType()

    # Templates are created from the same selection.
    assert ids(export_job_type.fetch_applications(user, workspace, [])) == [database.id]
    with pytest.raises(PermissionDenied):
        export_job_type.fetch_applications(user, workspace, [shared_application.id])


@pytest.mark.django_db
def test_user_template_with_only_a_shared_application_has_no_content(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(name="Content")
    data_fixture.create_shared_application(workspace=workspace)
    revision = data_fixture.create_user_template(
        user=user, workspace=workspace, icon="iconoir-view-grid"
    )

    with pytest.raises(TemplateHasNoContent):
        UserTemplateHandler().serialize_template_content(revision)
    with pytest.raises(TemplateHasNoContent):
        UserTemplateHandler().get_installable_revision(user, revision, latest=True)


@pytest.mark.django_db
def test_trash_structure_leaves_the_shared_application_out(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_shared_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace, order=1)

    structure = TrashHandler.get_trash_structure(user)

    assert [
        ids(workspace_structure["applications"])
        for workspace_structure in structure["workspaces"]
    ] == [[database.id]]


@pytest.mark.django_db
def test_application_tools_leave_the_shared_application_out(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_shared_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace, order=1)
    ctx = ToolContext(user=user, workspace=workspace)

    assert ids(visible_applications(ctx)) == [database.id]
    assert ids(visible_applications(ctx, [SharedApplicationType.type])) == []


@pytest.mark.django_db
def test_new_workspace_gets_its_shared_application(data_fixture):
    user = data_fixture.create_user()

    workspace = CoreHandler().create_workspace(user, "Workspace").workspace

    (shared_application,) = SharedApplication.objects.filter(workspace=workspace)
    assert shared_application.name == SHARED_APPLICATION_NAME
    assert shared_application.order == 0


@pytest.mark.django_db
def test_listing_creates_the_missing_shared_application_once(data_fixture):
    workspace = data_fixture.create_workspace()
    database = data_fixture.create_database_application(workspace=workspace, order=1)

    listed = ids(CoreHandler().list_applications_in_workspace(workspace))

    (shared_application,) = SharedApplication.objects.filter(workspace=workspace)
    assert listed == [shared_application.id, database.id]
    assert ids(CoreHandler().list_applications_in_workspace(workspace)) == listed
    assert SharedApplication.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
def test_create_missing_shared_applications_skips_existing_and_trashed(data_fixture):
    workspace = data_fixture.create_workspace()
    shared_application = data_fixture.create_shared_application()
    trashed_workspace = data_fixture.create_workspace(trashed=True)

    created = CoreHandler().create_missing_shared_applications(
        [workspace.id, shared_application.workspace_id, trashed_workspace.id]
    )

    assert [application.workspace_id for application in created] == [workspace.id]
    existing = SharedApplication.objects.filter(workspace=shared_application.workspace)
    assert ids(existing) == [shared_application.id]
    assert ids(trashed_workspace.application_set_including_trash().all()) == []


@pytest.mark.django_db
def test_create_all_missing_shared_applications_walks_every_workspace(data_fixture):
    workspaces = [data_fixture.create_workspace() for _ in range(3)]
    data_fixture.create_shared_application(workspace=workspaces[1])
    data_fixture.create_workspace(trashed=True)
    handler = CoreHandler()

    assert handler.create_all_missing_shared_applications(batch_size=1) == 2
    for workspace in workspaces:
        assert SharedApplication.objects.filter(workspace=workspace).count() == 1
    assert handler.create_all_missing_shared_applications() == 0


@pytest.mark.django_db
def test_create_all_missing_shared_applications_stops_at_the_deadline(data_fixture):
    workspaces = [data_fixture.create_workspace() for _ in range(3)]
    handler = CoreHandler()

    # The deadline hasn't passed before the first batch, and has before the second.
    with patch("baserow.core.handler.monotonic", side_effect=[0, 10]):
        created_count = handler.create_all_missing_shared_applications(
            batch_size=1, deadline=5
        )

    assert created_count == 1
    assert SharedApplication.objects.filter(workspace=workspaces[0]).count() == 1
    assert SharedApplication.objects.filter(workspace__in=workspaces[1:]).count() == 0
    # The next call creates the ones left.
    assert handler.create_all_missing_shared_applications() == 2


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
def test_create_all_missing_shared_applications_skips_a_locked_workspace(
    data_fixture,
):
    locked = data_fixture.create_workspace()
    free = data_fixture.create_workspace()
    handler = CoreHandler()

    # Fails instead of hanging if the backfill waits for the lock.
    with connection.cursor() as cursor:
        cursor.execute("SET lock_timeout = '5s'")
    try:
        # Another connection holds the workspace row, like renaming it would.
        with transaction.atomic(using="default-copy"):
            Workspace.objects.using("default-copy").select_for_update().get(
                id=locked.id
            )
            assert handler.create_all_missing_shared_applications() == 1
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET lock_timeout")

    assert SharedApplication.objects.filter(workspace=free).count() == 1
    assert SharedApplication.objects.filter(workspace=locked).count() == 0
    # The next call creates it once the lock is released.
    assert handler.create_all_missing_shared_applications() == 1
    assert SharedApplication.objects.filter(workspace=locked).count() == 1


@pytest.mark.django_db
def test_create_all_missing_shared_applications_with_a_passed_deadline(data_fixture):
    workspace = data_fixture.create_workspace()

    created_count = CoreHandler().create_all_missing_shared_applications(
        deadline=monotonic()
    )

    assert created_count == 0
    assert SharedApplication.objects.filter(workspace=workspace).count() == 0


@pytest.mark.django_db
def test_backfill_task_creates_the_missing_shared_applications(data_fixture):
    workspace = data_fixture.create_workspace()

    create_missing_shared_applications_task()

    assert SharedApplication.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
def test_backfill_task_stops_at_its_time_limit_without_raising(data_fixture):
    workspace = data_fixture.create_workspace()

    with patch("baserow.core.tasks.CREATE_MISSING_SHARED_APPLICATIONS_TIME_LIMIT", 0):
        create_missing_shared_applications_task()

    assert SharedApplication.objects.filter(workspace=workspace).count() == 0


def test_backfill_task_celery_limits_leave_room_for_its_own_deadline():
    # Without its own soft limit, the worker default (5 minutes) would cut a run
    # off before or at the same time as its deadline, and the run would fail.
    task = create_missing_shared_applications_task

    assert CREATE_MISSING_SHARED_APPLICATIONS_TIME_LIMIT < task.soft_time_limit
    assert task.soft_time_limit < task.time_limit <= task.lock_expiry


@pytest.mark.django_db
def test_permanently_deleting_a_workspace_deletes_its_shared_application(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = CoreHandler().create_workspace(user, "Workspace").workspace
    shared_application = SharedApplication.objects.get(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=shared_application, user=user
    )

    TrashHandler.permanently_delete(workspace)

    assert not Application.objects_and_trash.filter(id=shared_application.id).exists()
    assert not Integration.objects_and_trash.filter(id=integration.id).exists()
