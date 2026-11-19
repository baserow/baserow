"""
How the workspace integrations an application uses travel when it's copied:
publishing, workspace exports and templates give the copy integrations of its
own, while duplicates and snapshots stay in the workspace and keep referring to
them.
"""

from copy import deepcopy
from io import BytesIO

import pytest

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.utils import Progress

FILE = ImportExportConfig(include_permission_data=False)
TEMPLATE = ImportExportConfig(
    include_permission_data=False, is_duplicate=True, is_template=True
)


def _workspace_integration(data_fixture, workspace, user):
    return data_fixture.create_local_baserow_integration(
        application=data_fixture.create_shared_application(workspace=workspace),
        authorized_user=user,
        name="Shared",
    )


def _builder_using(data_fixture, workspace, integration):
    builder = data_fixture.create_builder_application(workspace=workspace, order=1)
    data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=data_fixture.create_builder_page(builder=builder),
        integration=integration,
    )
    return builder


def _data_source_integration_id(builder_id):
    (data_source,) = DataSource.objects.filter(page__builder_id=builder_id)
    return data_source.service.integration_id


@pytest.mark.django_db
def test_publishing_a_builder_copies_its_workspace_integrations(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    builder = _builder_using(data_fixture, workspace, integration)
    domain = data_fixture.create_builder_custom_domain(builder=builder)

    published_builder = DomainHandler().publish(domain).published_to

    # A published copy has no workspace to read the original from.
    (copy,) = published_builder.integrations.all()
    assert copy.id != integration.id
    assert copy.name == "Shared"
    assert _data_source_integration_id(published_builder.id) == copy.id
    # Publishing keeps who the integration reads as, like for the builder's own.
    assert copy.specific.authorized_subject_id == user.id


@pytest.mark.django_db
def test_duplicating_a_builder_keeps_its_workspace_integrations(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    builder = _builder_using(data_fixture, workspace, integration)

    duplicated = CoreHandler().duplicate_application(user, builder)

    assert not duplicated.integrations.exists()
    assert _data_source_integration_id(duplicated.id) == integration.id


@pytest.mark.django_db
def test_a_builder_snapshot_and_its_restore_keep_its_workspace_integrations(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    builder = _builder_using(data_fixture, workspace, integration)
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=builder, name="snap", created_by=user
    )

    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()

    # The snapshot has no workspace, but still refers to the integration.
    assert _data_source_integration_id(snapshot.snapshot_to_application_id) == (
        integration.id
    )

    restored = SnapshotHandler().perform_restore(snapshot, Progress(total=100))

    assert not restored.integrations.exists()
    assert _data_source_integration_id(restored.id) == integration.id


@pytest.mark.django_db
def test_a_workspace_export_copies_the_workspace_integrations_of_a_builder(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    _builder_using(data_fixture, workspace, integration)
    core_handler = CoreHandler()

    (exported_builder,) = core_handler.export_workspace_applications(
        workspace, BytesIO(), FILE
    )

    assert [i["id"] for i in exported_builder["integrations"]] == [integration.id]

    # Even into its own workspace, the import gets a copy of its own.
    for target in [data_fixture.create_workspace(user=user), workspace]:
        (imported,), _ = core_handler.import_applications_to_workspace(
            target, [deepcopy(exported_builder)], BytesIO(), FILE, None
        )

        (copy,) = imported.integrations.all()
        assert copy.id != integration.id
        assert _data_source_integration_id(imported.id) == copy.id


@pytest.mark.django_db
def test_a_template_gets_copies_of_the_workspace_integrations_it_was_written_with(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    _builder_using(data_fixture, workspace, integration)
    core_handler = CoreHandler()
    # Templates are written by a workspace export.
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), FILE)

    (installed,), _ = core_handler.import_applications_to_workspace(
        data_fixture.create_workspace(user=user), exported, BytesIO(), TEMPLATE, None
    )

    (copy,) = installed.integrations.all()
    assert _data_source_integration_id(installed.id) == copy.id


@pytest.mark.django_db
def test_a_template_drops_a_workspace_integration_it_does_not_carry(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    builder = _builder_using(data_fixture, workspace, integration)
    # Written on another installation, the id names whatever has it here.
    serialized = builder.get_type().export_serialized(
        builder, ImportExportConfig(include_permission_data=False, is_duplicate=True)
    )

    (installed,), _ = CoreHandler().import_applications_to_workspace(
        workspace, [serialized], BytesIO(), TEMPLATE, None
    )

    assert _data_source_integration_id(installed.id) is None


def _workflow_using(data_fixture, workspace, integration):
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(automation=automation)
    data_fixture.create_automation_node(
        workflow=workflow,
        type="local_baserow_list_rows",
        reference_node_id=workflow.get_trigger().id,
        service_kwargs={"integration": integration},
    )
    return workflow


def _list_rows_integration(workflow):
    (node,) = [
        node
        for node in AutomationNodeHandler().get_nodes(workflow=workflow)
        if node.get_type().type == "local_baserow_list_rows"
    ]
    return node.service.integration


@pytest.mark.django_db
def test_publishing_a_workflow_copies_its_workspace_integrations(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    workflow = _workflow_using(data_fixture, workspace, integration)

    published_workflow = AutomationWorkflowHandler().publish(workflow)

    copy = _list_rows_integration(published_workflow)
    assert copy.id != integration.id
    assert copy.application_id == published_workflow.automation_id
    assert copy.specific.authorized_subject_id == user.id


@pytest.mark.django_db
def test_duplicating_an_automation_keeps_its_workspace_integrations(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    workflow = _workflow_using(data_fixture, workspace, integration)

    duplicated = CoreHandler().duplicate_application(user, workflow.automation)

    assert _list_rows_integration(duplicated.workflows.get()).id == integration.id


def _dashboard_using(data_fixture, workspace, integration):
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard, integration=integration
    )
    return dashboard


@pytest.mark.django_db
def test_duplicating_a_dashboard_keeps_its_workspace_integrations(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    dashboard = _dashboard_using(data_fixture, workspace, integration)

    duplicated = CoreHandler().duplicate_application(user, dashboard)

    (data_source,) = DashboardDataSource.objects.filter(dashboard=duplicated)
    assert data_source.service.integration_id == integration.id


@pytest.mark.django_db
def test_a_workspace_export_copies_the_workspace_integrations_of_a_dashboard(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = _workspace_integration(data_fixture, workspace, user)
    _dashboard_using(data_fixture, workspace, integration)
    core_handler = CoreHandler()

    exported = core_handler.export_workspace_applications(workspace, BytesIO(), FILE)
    (imported,), _ = core_handler.import_applications_to_workspace(
        data_fixture.create_workspace(user=user), exported, BytesIO(), FILE, None
    )

    (copy,) = imported.integrations.all()
    (data_source,) = DashboardDataSource.objects.filter(dashboard=imported)
    assert copy.id != integration.id
    assert data_source.service.integration_id == copy.id
