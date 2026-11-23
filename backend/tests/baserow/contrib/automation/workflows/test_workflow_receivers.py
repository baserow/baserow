import pytest

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.constants import WORKFLOW_DIRTY_CACHE_KEY
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.cache import global_cache
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.service import IntegrationService
from baserow.core.trash.handler import TrashHandler


def _is_marked_changed(workflow):
    return global_cache.get(WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id), default=False)


def _action_integration_id(workflow):
    """The integration of the one node after the trigger."""

    return (
        AutomationNode.objects.filter(workflow=workflow)
        .exclude(id=workflow.get_trigger().id)
        .get()
        .service.integration_id
    )


def _workflow_using_an_integration(data_fixture, owner):
    """
    A workflow whose action node uses an integration of its automation, or of its
    workspace, after a test run that left a copy to reuse.
    """

    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    application = (
        workflow.automation
        if owner == "automation"
        else data_fixture.create_shared_application(
            workspace=workflow.automation.workspace
        )
    )
    integration = data_fixture.create_local_baserow_integration(
        application=application, authorized_user=user
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, service_kwargs={"integration": integration}
    )
    AutomationWorkflowHandler()._ensure_published_for_run(workflow)
    assert not _is_marked_changed(workflow)

    return user, workflow, integration


@pytest.mark.django_db
@pytest.mark.parametrize("owner", ["automation", "workspace"])
def test_deleting_an_integration_makes_the_next_test_run_use_a_new_copy(
    data_fixture, owner
):
    user, workflow, integration = _workflow_using_an_integration(data_fixture, owner)
    handler = AutomationWorkflowHandler()
    copy_before = handler._ensure_published_for_run(workflow)
    assert _action_integration_id(copy_before) is not None

    IntegrationService().delete_integration(
        user, IntegrationHandler().get_integration_for_update(integration.id)
    )

    assert _is_marked_changed(workflow)
    copy_after = handler._ensure_published_for_run(workflow)
    assert copy_after.id != copy_before.id
    # The trashed integration isn't copied, so the test run fails instead of
    # using it.
    assert _action_integration_id(copy_after) is None


@pytest.mark.django_db
@pytest.mark.parametrize("owner", ["automation", "workspace"])
def test_restoring_an_integration_marks_the_workflows_using_it_changed(
    data_fixture, owner
):
    user, workflow, integration = _workflow_using_an_integration(data_fixture, owner)
    IntegrationService().delete_integration(
        user, IntegrationHandler().get_integration_for_update(integration.id)
    )
    AutomationWorkflowHandler()._ensure_published_for_run(workflow)
    assert not _is_marked_changed(workflow)

    TrashHandler.restore_item(user, "integration", integration.id)

    assert _is_marked_changed(workflow)


@pytest.mark.django_db
@pytest.mark.parametrize("owner", ["automation", "workspace"])
def test_updating_an_integration_marks_the_workflows_using_it_changed(
    data_fixture, owner
):
    user, workflow, integration = _workflow_using_an_integration(data_fixture, owner)

    IntegrationService().update_integration(
        user,
        IntegrationHandler().get_integration_for_update(integration.id),
        name="Renamed",
    )

    assert _is_marked_changed(workflow)


@pytest.mark.django_db
def test_changing_an_integration_leaves_the_workflows_not_using_it(data_fixture):
    user, workflow, integration = _workflow_using_an_integration(
        data_fixture, "workspace"
    )
    other_integration = data_fixture.create_local_baserow_integration(
        application=integration.application, authorized_user=user
    )

    IntegrationService().update_integration(
        user,
        IntegrationHandler().get_integration_for_update(other_integration.id),
        name="Renamed",
    )
    IntegrationService().delete_integration(
        user, IntegrationHandler().get_integration_for_update(other_integration.id)
    )

    assert not _is_marked_changed(workflow)
