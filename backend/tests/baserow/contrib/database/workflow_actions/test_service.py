from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

import pytest

from baserow.contrib.database.workflow_actions.actions import (
    DispatchButtonFieldActionType,
)
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
)
from baserow.contrib.database.workflow_actions.models import (
    ButtonFieldDispatchJob,
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.signals import (
    workflow_action_deleted,
)
from baserow.core.action.signals import action_done
from baserow.core.exceptions import PermissionException
from baserow.core.jobs.constants import (
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
    JOB_STARTED,
)
from baserow.core.services.models import Service


@pytest.mark.django_db
def test_create_workflow_action(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    action = DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field
    )

    assert action.field_id == button_field.id
    assert action.service is not None


@pytest.mark.django_db
def test_create_is_refused_without_field_permission(data_fixture):
    outsider = data_fixture.create_user()
    owner = data_fixture.create_user()
    table = data_fixture.create_database_table(user=owner)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().create_workflow_action(
            outsider, action_type, button_field
        )


@pytest.mark.django_db
def test_delete_is_refused_without_field_permission(data_fixture):
    outsider = data_fixture.create_user()
    owner = data_fixture.create_user()
    table = data_fixture.create_database_table(user=owner)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().delete_workflow_action(outsider, action)


@pytest.mark.django_db
def test_delete_sends_the_deleted_action_id(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action_id = action.id
    received = []

    def receiver(sender, **kwargs):
        received.append(kwargs)

    workflow_action_deleted.connect(receiver)
    try:
        DatabaseWorkflowActionService().delete_workflow_action(user, action)
    finally:
        workflow_action_deleted.disconnect(receiver)

    assert len(received) == 1
    assert received[0]["workflow_action_id"] == action_id


@pytest.mark.django_db(transaction=True)
def test_deleting_an_action_trashes_it_and_keeps_its_service(data_fixture):
    """Kept until the trash is emptied, so an undo restores the action whole."""

    from baserow.core.services.models import Service

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service_id = action.service_id

    DatabaseWorkflowActionService().delete_workflow_action(user, action)

    assert not DatabaseWorkflowAction.objects.filter(id=action.id).exists()
    assert DatabaseWorkflowAction.trash.filter(id=action.id).exists()
    assert Service.objects.filter(id=service_id).exists()


@pytest.mark.django_db
def test_changing_the_type_keeps_the_action(data_fixture):
    """A type change is an update, so the caller keeps the action it had."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action_id, order, old_service_id = action.id, action.order, action.service_id

    updated = (
        DatabaseWorkflowActionService()
        .update_workflow_action(user, action, type="local_baserow_delete_row")
        .workflow_action
    )

    assert isinstance(updated, LocalBaserowDeleteRowWorkflowAction)
    assert updated.id == action_id
    assert updated.order == order
    assert updated.field_id == button_field.id
    assert updated.service_id != old_service_id
    assert DatabaseWorkflowAction.objects.filter(field=button_field).count() == 1


@pytest.mark.django_db
def test_changing_the_type_disposes_the_old_service(data_fixture):
    """The swap only deletes the child row, so `pre_delete` never fires."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    old_service_id = action.service_id

    DatabaseWorkflowActionService().update_workflow_action(
        user, action, type="open_url"
    )

    assert not Service.objects.filter(id=old_service_id).exists()


@pytest.mark.django_db
def test_changing_the_type_drops_the_old_type_values(data_fixture):
    """The old type's row goes with it, so its values can't reach the new one."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"mode": "simple", "version": "0.1", "formula": "'https://baserow.io'"},
    )

    updated = (
        DatabaseWorkflowActionService()
        .update_workflow_action(user, action, type="local_baserow_create_row")
        .workflow_action
    )

    assert isinstance(updated, LocalBaserowCreateRowWorkflowAction)
    assert updated.service_id is not None
    assert not OpenUrlWorkflowAction.objects.filter(id=updated.id).exists()


@pytest.mark.django_db
def test_changing_the_type_holds_its_place_in_the_order(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    middle = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    last = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().update_workflow_action(
        user, middle, type="open_url"
    )

    assert list(
        DatabaseWorkflowAction.objects.filter(field=button_field)
        .order_by("order", "id")
        .values_list("id", flat=True)
    ) == [first.id, middle.id, last.id]


@pytest.mark.django_db
def test_order_workflow_actions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().order_workflow_actions(
        user, button_field, [second.id, first.id]
    )
    first.refresh_from_db()
    second.refresh_from_db()

    assert second.order < first.order


@pytest.mark.django_db
def test_check_dispatch_allowed_refuses_a_user_outside_the_workspace(data_fixture):
    user = data_fixture.create_user()
    outsider = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().check_dispatch_allowed(
            outsider, button_field, [action]
        )


@pytest.fixture
def audited_clicks():
    """The `action_params` of every button click registration."""

    received = []

    def receiver(sender, action_type, action_params, **kwargs):
        if action_type is DispatchButtonFieldActionType:
            received.append(action_params)

    action_done.connect(receiver)
    yield received
    action_done.disconnect(receiver)


@pytest.mark.django_db
def test_check_dispatch_allowed_refuses_a_misconfigured_action_by_position(
    data_fixture, audited_clicks
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    fine = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    # An update-row action with no row id formula is misconfigured.
    broken = data_fixture.create_database_workflow_action(
        LocalBaserowUpdateRowWorkflowAction, field=button_field
    )

    with pytest.raises(WorkflowActionDispatchError) as raised:
        DatabaseWorkflowActionService().check_dispatch_allowed(
            user, button_field, [fine, broken]
        )

    assert raised.value.position == 2
    # A refusal leaves no audit entry for the click.
    assert audited_clicks == []


@pytest.mark.django_db
def test_dispatch_positions_count_every_action_from_one(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    first = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    positions = DatabaseWorkflowActionService().dispatch_positions([first, second])

    assert positions == {first.id: 1, second.id: 2}


@pytest.mark.django_db
def test_has_click_in_flight_sees_only_pending_and_started_jobs(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    service = DatabaseWorkflowActionService()

    def busy(row_id):
        return service.has_click_in_flight(button_field, row_id, [])

    assert not busy(1)

    for state in (JOB_FINISHED, JOB_FAILED):
        ButtonFieldDispatchJob.objects.create(
            user=user, field=button_field, row_id=1, state=state
        )
    assert not busy(1)

    ButtonFieldDispatchJob.objects.create(
        user=user, field=button_field, row_id=1, state=JOB_PENDING
    )
    assert busy(1)
    # Another cell of the same button is free.
    assert not busy(2)

    ButtonFieldDispatchJob.objects.create(
        user=user, field=button_field, row_id=2, state=JOB_STARTED
    )
    assert busy(2)


@pytest.mark.django_db
@override_settings(
    DATABASE_BUTTON_DISPATCH_LOCK_TTL_SECONDS=120, BASEROW_JOB_SOFT_TIME_LIMIT=1800
)
def test_a_click_job_left_behind_by_a_dead_worker_frees_its_cell(data_fixture):
    """A killed worker never moves its job out of started, and a lost queue
    message never moves one out of pending. Each counts only for as long as
    it could legitimately last, so the cell is not blocked until cleanup."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    service = DatabaseWorkflowActionService()
    now = timezone.now()

    def job_updated(row_id, state, seconds_ago):
        job = ButtonFieldDispatchJob.objects.create(
            user=user, field=button_field, row_id=row_id, state=state
        )
        # `updated_on` is set on save, so aged afterwards.
        ButtonFieldDispatchJob.objects.filter(id=job.id).update(
            updated_on=now - timedelta(seconds=seconds_ago)
        )

    job_updated(1, JOB_STARTED, 119)
    job_updated(2, JOB_STARTED, 121)
    job_updated(3, JOB_PENDING, 121)
    job_updated(4, JOB_PENDING, 1801)

    assert service.has_click_in_flight(button_field, 1, [])
    assert not service.has_click_in_flight(button_field, 2, [])
    # Still waiting in a backed-up queue, well past a running click's TTL.
    assert service.has_click_in_flight(button_field, 3, [])
    assert not service.has_click_in_flight(button_field, 4, [])
