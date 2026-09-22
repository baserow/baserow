from collections import defaultdict
from unittest.mock import patch

import pytest
from rest_framework import serializers

from baserow.contrib.automation.nodes.node_types import (
    CoreManualTriggerNodeType,
    CorePeriodicTriggerNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.core.service_types import CoreStartWorkflowServiceType
from baserow.core.deferred_callbacks import deferred_callback_context
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.utils import MirrorDict
from baserow.test_utils.pytest_conftest import FakeDispatchContext


def fake_dispatch_context(workflow=None):
    """A context running in the workspace of `workflow`, or in none."""

    return FakeDispatchContext(
        count=None,
        is_publicly_searchable=False,
        searchable_fields=None,
        is_publicly_filterable=False,
        is_publicly_sortable=False,
        workspace=workflow.automation.workspace if workflow else None,
    )


def _workflow(data_fixture, user, workspace=None, **kwargs):
    automation = data_fixture.create_automation_application(
        user=user, **({"workspace": workspace} if workspace else {})
    )
    kwargs.setdefault("trigger_type", CoreManualTriggerNodeType.type)
    return data_fixture.create_automation_workflow(
        user=user, automation=automation, **kwargs
    )


def _copy_config(**kwargs) -> ImportExportConfig:
    """What a copy that stays inside the instance is imported with."""

    return ImportExportConfig(
        include_permission_data=True,
        reduce_disk_space_usage=False,
        exclude_sensitive_data=False,
        **kwargs,
    )


def _import(service, id_mapping, import_export_config=None):
    """
    Imports an export of `service` the way a copy that stays inside the
    instance is imported: outside any deferred callback context, so the
    workflow is decided at once.
    """

    service_type = CoreStartWorkflowServiceType()
    exported = service_type.export_serialized(service)
    return service_type.import_serialized(
        None, exported, id_mapping, import_export_config=import_export_config
    )


@pytest.mark.django_db
def test_start_workflow_service_generate_schema_returns_none(data_fixture):
    service = data_fixture.create_core_start_workflow_service()

    assert CoreStartWorkflowServiceType().generate_schema(service) is None


@pytest.mark.django_db
def test_start_workflow_service_import_serialized_remaps_workflow_id(data_fixture):
    user = data_fixture.create_user()
    original_workflow = _workflow(data_fixture, user)
    imported_workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(
        workflow=original_workflow
    )

    imported_service = _import(
        service, {"automation_workflows": {original_workflow.id: imported_workflow.id}}
    )

    assert imported_service.workflow_id == imported_workflow.id


@pytest.mark.django_db
def test_start_workflow_service_dispatch_starts_configured_workflow(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with patch(
        "baserow.contrib.automation.workflows.handler."
        "AutomationWorkflowHandler.async_start_workflow"
    ) as async_start_workflow:
        result = ServiceHandler().dispatch_service(
            service, fake_dispatch_context(workflow)
        )

    async_start_workflow.assert_called_once_with(published_workflow, triggered_by=None)
    assert result.data is None


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_allows_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CorePeriodicTriggerNodeType.type
    )
    AutomationWorkflowHandler().publish(workflow)

    values = CoreStartWorkflowServiceType().prepare_values(
        {"workflow_id": workflow.id}, user
    )

    assert values["workflow"] == workflow


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_rejects_workflow_without_trigger(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user, create_trigger=False)
    AutomationWorkflowHandler().publish(workflow)

    with pytest.raises(serializers.ValidationError) as exc:
        CoreStartWorkflowServiceType().prepare_values(
            {"workflow_id": workflow.id}, user
        )

    assert (
        exc.value.detail[0] == CoreStartWorkflowServiceType.TRIGGER_NOT_ON_DEMAND_ERROR
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_starts_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CorePeriodicTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with patch(
        "baserow.contrib.automation.workflows.handler."
        "AutomationWorkflowHandler.async_start_workflow"
    ) as async_start_workflow:
        result = ServiceHandler().dispatch_service(
            service, fake_dispatch_context(workflow)
        )

    async_start_workflow.assert_called_once_with(published_workflow, triggered_by=None)
    assert result.data is None


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_rejects_non_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    table, _, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Blueberry Muffin"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={"table": table},
    )
    AutomationWorkflowHandler().publish(workflow)

    with pytest.raises(serializers.ValidationError) as exc:
        CoreStartWorkflowServiceType().prepare_values(
            {"workflow_id": workflow.id}, user
        )

    assert (
        exc.value.detail[0] == CoreStartWorkflowServiceType.TRIGGER_NOT_ON_DEMAND_ERROR
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_non_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    table, _, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Blueberry Muffin"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={"table": table},
    )
    AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, fake_dispatch_context(workflow))

    assert str(exc.value) == CoreStartWorkflowServiceType.TRIGGER_NOT_ON_DEMAND_ERROR


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_unpublished_workflow(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, fake_dispatch_context(workflow))

    assert (
        str(exc.value)
        == "The selected workflow must be published before it can be started."
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_disabled_published_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    published_workflow.state = WorkflowState.DISABLED
    published_workflow.save(update_fields=["state"])
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(service, fake_dispatch_context(workflow))


@pytest.mark.django_db
def test_start_workflow_service_dispatch_without_workflow_raises(data_fixture):
    service = data_fixture.create_core_start_workflow_service(workflow=None)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(service, fake_dispatch_context())


@pytest.mark.django_db
def test_start_workflow_service_dispatch_names_the_context_actor(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)
    dispatch_context = fake_dispatch_context(workflow)
    dispatch_context.actor = user

    with patch(
        "baserow.contrib.automation.workflows.handler."
        "AutomationWorkflowHandler.async_start_workflow"
    ) as async_start_workflow:
        ServiceHandler().dispatch_service(service, dispatch_context)

    async_start_workflow.assert_called_once_with(published_workflow, triggered_by=user)


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_workflow_from_another_workspace(
    data_fixture,
):
    """
    A user can be in more than one workspace, and an import used to keep
    whatever workflow id the file named, so the run checks what save checks:
    the workflow lives in the workspace the service runs in.
    """

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)
    elsewhere = data_fixture.create_workspace(user=user)

    with (
        patch(
            "baserow.contrib.automation.workflows.handler."
            "AutomationWorkflowHandler.async_start_workflow"
        ) as async_start_workflow,
        pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc,
    ):
        ServiceHandler().dispatch_service(
            service, FakeDispatchContext(workspace=elsewhere)
        )

    assert str(
        exc.value
    ) == CoreStartWorkflowServiceType.WORKFLOW_DOES_NOT_EXIST_ERROR.format(
        workflow_id=workflow.id
    )
    async_start_workflow.assert_not_called()


@pytest.mark.django_db
def test_start_workflow_service_dispatch_needs_a_workspace(data_fixture):
    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(service, fake_dispatch_context())


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_refuses_a_workflow_the_user_cannot_read(
    data_fixture,
):
    """A refusal reads like a missing workflow, so it reveals nothing."""

    owner = data_fixture.create_user()
    workflow = _workflow(data_fixture, owner)
    outsider = data_fixture.create_user()

    with pytest.raises(serializers.ValidationError) as exc:
        CoreStartWorkflowServiceType().prepare_values(
            {"workflow_id": workflow.id}, outsider
        )

    assert exc.value.detail[
        0
    ] == CoreStartWorkflowServiceType.WORKFLOW_DOES_NOT_EXIST_ERROR.format(
        workflow_id=workflow.id
    )


@pytest.mark.django_db
def test_start_workflow_service_get_workflow_to_start_reads_the_workspace(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    elsewhere = data_fixture.create_workspace(user=user)
    service_type = CoreStartWorkflowServiceType()

    with pytest.raises(serializers.ValidationError) as exc:
        service_type.get_workflow_to_start(user, workflow.id, elsewhere.id)

    assert exc.value.detail[
        0
    ] == CoreStartWorkflowServiceType.WORKFLOW_DOES_NOT_EXIST_ERROR.format(
        workflow_id=workflow.id
    )
    assert (
        service_type.get_workflow_to_start(
            user, workflow.id, workflow.automation.workspace_id
        )
        == workflow
    )


@pytest.mark.django_db
def test_start_workflow_service_import_drops_a_remapped_workflow_not_on_demand(
    data_fixture,
):
    user = data_fixture.create_user()
    original_workflow = _workflow(data_fixture, user)
    table = data_fixture.create_database_table(user=user)
    imported_workflow = _workflow(
        data_fixture,
        user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={"table": table},
    )
    service = data_fixture.create_core_start_workflow_service(
        workflow=original_workflow
    )

    imported_service = _import(
        service, {"automation_workflows": {original_workflow.id: imported_workflow.id}}
    )

    assert imported_service.workflow_id is None


@pytest.mark.django_db
def test_start_workflow_service_import_drops_an_unmapped_workflow_from_a_file(
    data_fixture,
):
    """
    Ids are one global sequence, so a file written on another installation
    can name a workflow id this installation happens to own. Living here is
    not the same as being the workflow somebody chose: kept, the service would
    start work nobody picked, in a workspace the file never came from.
    """

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    imported_service = _import(
        service, {}, ImportExportConfig(include_permission_data=False)
    )

    assert imported_service.workflow_id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "import_export_config",
    [_copy_config(is_duplicate=True), _copy_config(is_publishing=True)],
)
def test_start_workflow_service_import_keeps_an_unmapped_workflow_of_a_copy(
    data_fixture, import_export_config
):
    """
    A duplicate, a snapshot or a publication never leaves the instance, so
    the id it carries is the workflow somebody chose.
    """

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    imported_service = _import(service, {}, import_export_config)

    assert imported_service.workflow_id == workflow.id


@pytest.mark.django_db
def test_start_workflow_service_import_drops_an_unmapped_workflow_of_a_template(
    data_fixture,
):
    """A template install says duplicate too, but its ids were written elsewhere."""

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    imported_service = _import(
        service, {}, _copy_config(is_duplicate=True, is_template=True)
    )

    assert imported_service.workflow_id is None


@pytest.mark.django_db
def test_start_workflow_service_import_drops_a_workflow_from_another_workspace(
    data_fixture,
):
    """A snapshot restore and a publication name the workspace they import into."""

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)
    elsewhere = data_fixture.create_workspace(user=user)

    imported_service = _import(
        service,
        {"import_workspace_id": elsewhere.id},
        _copy_config(is_duplicate=True),
    )

    assert imported_service.workflow_id is None


@pytest.mark.django_db
def test_start_workflow_service_import_drops_a_workflow_the_copier_cannot_read(
    data_fixture,
):
    owner = data_fixture.create_user()
    workflow = _workflow(data_fixture, owner)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)
    outsider = data_fixture.create_user()

    imported_service = _import(
        service, {}, _copy_config(is_duplicate=True, copied_by=outsider)
    )

    assert imported_service.workflow_id is None


@pytest.mark.django_db
def test_start_workflow_service_import_keeps_a_duplicated_workflow_mapping(
    data_fixture,
):
    """
    What `AutomationWorkflowHandler.duplicate_workflow` builds: a `MirrorDict`
    under the very key, which answers `in` for every id but names nothing it
    remapped. The copy keeps the workflow; a file with the same mapping shape
    still does not.
    """

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)
    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["automation_workflows"] = MirrorDict()

    duplicated = _import(service, id_mapping, _copy_config(is_duplicate=True))
    from_file = _import(
        service, id_mapping, ImportExportConfig(include_permission_data=False)
    )

    assert duplicated.workflow_id == workflow.id
    assert from_file.workflow_id is None


@pytest.mark.django_db
def test_start_workflow_service_import_waits_for_the_workflow_mapping(data_fixture):
    """
    A workspace import brings the builder in before the automation, so the
    workflow an action names has no copy yet when its service is imported.
    Inside a deferred callback context the decision waits until the context
    exits, by which point the automation has registered its mapping.
    """

    user = data_fixture.create_user()
    original_workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(
        workflow=original_workflow
    )
    service_type = CoreStartWorkflowServiceType()
    exported = service_type.export_serialized(service)
    id_mapping = {"automation_workflows": {}}

    with deferred_callback_context():
        imported_service = service_type.import_serialized(None, exported, id_mapping)
        assert imported_service.workflow_id is None
        imported_workflow = _workflow(data_fixture, user)
        id_mapping["automation_workflows"][original_workflow.id] = imported_workflow.id

    imported_service.refresh_from_db()
    assert imported_service.workflow_id == imported_workflow.id


@pytest.mark.django_db
def test_start_workflow_service_import_drops_a_workflow_no_application_brought(
    data_fixture,
):
    """
    Exporting only the builder leaves the automation behind, so nothing in
    the import ever registers the id the file named.
    """

    user = data_fixture.create_user()
    workflow = _workflow(data_fixture, user)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)
    service_type = CoreStartWorkflowServiceType()
    exported = service_type.export_serialized(service)

    with deferred_callback_context():
        imported_service = service_type.import_serialized(
            None,
            exported,
            {},
            import_export_config=ImportExportConfig(include_permission_data=False),
        )

    imported_service.refresh_from_db()
    assert imported_service.workflow_id is None
