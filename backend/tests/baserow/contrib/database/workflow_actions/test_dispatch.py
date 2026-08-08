from django.core.cache import cache

import pytest

from baserow.contrib.database.rows.signals import rows_created
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
)
from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.exceptions import PermissionException


def _table_with_name(data_fixture, user, name="People"):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name=name, fields=[("Name", "text", {})]
    )
    return table, table.field_set.get(name="Name")


def _create_row_action(data_fixture, button_field, table, name_field, value):
    action = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value=f"'{value}'", enabled=True)
    return action


@pytest.mark.django_db
def test_the_actions_run_in_order(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")
    _create_row_action(data_fixture, button_field, table, name_field, "second")

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    created = [
        getattr(r, f"field_{name_field.id}")
        for r in table.get_model().objects.exclude(id=row.id).order_by("id")
    ]
    assert created == ["first", "second"]


@pytest.mark.django_db
def test_a_failure_keeps_the_completed_actions_and_skips_the_rest(data_fixture):
    """ADR 006 section 3: completed actions stay. This test fails if the
    sequence is ever wrapped in a transaction."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    _create_row_action(data_fixture, button_field, table, name_field, "first")
    # A delete-row action with no table configured fails at dispatch.
    broken = data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field
    )
    _create_row_action(data_fixture, button_field, table, name_field, "third")

    with pytest.raises(WorkflowActionDispatchError) as exc:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert exc.value.workflow_action_id == broken.id
    # Second of the three, counted the way the editor lists them.
    assert exc.value.position == 2

    created = [
        getattr(r, f"field_{name_field.id}")
        for r in table.get_model().objects.exclude(id=row.id)
    ]
    assert created == ["first"], (
        "The first action's row must survive the second action failing. If this "
        "reads [] the sequence has been wrapped in a transaction, which ADR 006 "
        "section 3 forbids."
    )


@pytest.mark.django_db
def test_an_action_can_target_the_clicked_row(data_fixture):
    """The archetypal button: "approve this row". `row_id` is a formula, so the
    only way to name the clicked row is through the row data provider."""

    from baserow.contrib.database.workflow_actions.models import (
        UpdateRowWorkflowAction,
    )

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Approve")
    model = table.get_model()
    row = model.objects.create(**{f"field_{name_field.id}": "pending"})
    other_row = model.objects.create(**{f"field_{name_field.id}": "untouched"})

    action = data_fixture.create_database_workflow_action(
        UpdateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.row_id = "get('row.id')"
    service.save()
    service.field_mappings.create(field=name_field, value="'approved'", enabled=True)

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    row.refresh_from_db()
    other_row.refresh_from_db()
    assert getattr(row, f"field_{name_field.id}") == "approved"
    assert getattr(other_row, f"field_{name_field.id}") == "untouched"


@pytest.mark.django_db
def test_a_concurrent_click_is_rejected(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")

    cache.add(f"button_dispatch_{button_field.id}_{row.id}", True, timeout=30)

    with pytest.raises(WorkflowActionDispatchInProgress):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert table.get_model().objects.exclude(id=row.id).count() == 0


@pytest.mark.django_db
def test_a_click_landing_mid_sequence_is_rejected(data_fixture):
    """Mutual exclusion, the point of the lock. The other lock tests seed the
    key themselves, so only this one proves `cache.add` really wrote it before
    the loop started."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")
    service = DatabaseWorkflowActionService()
    attempts = []

    def click_again(sender, **kwargs):
        # Without the guard, an implementation that took no lock would
        # recurse forever here instead of failing the assertions below.
        if attempts:
            return
        attempts.append(None)
        try:
            service.dispatch_workflow_actions(user, button_field, row)
        except Exception as exc:
            attempts[0] = exc

    rows_created.connect(click_again)
    try:
        service.dispatch_workflow_actions(user, button_field, row)
    finally:
        rows_created.disconnect(click_again)

    assert attempts, "The first action never ran, so nothing clicked again."
    assert isinstance(attempts[0], WorkflowActionDispatchInProgress), (
        "A second click arriving while the sequence is running must be "
        f"rejected, got {attempts[0]!r}. If nothing was raised the lock is "
        "never taken and a double click runs the sequence twice."
    )
    # The rejected click ran nothing, so only the outer click's row exists.
    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
def test_the_lock_is_released_after_a_success(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")
    service = DatabaseWorkflowActionService()

    service.dispatch_workflow_actions(user, button_field, row)
    service.dispatch_workflow_actions(user, button_field, row)

    assert table.get_model().objects.exclude(id=row.id).count() == 2


@pytest.mark.django_db
def test_the_lock_is_released_after_a_failure(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field
    )

    service = DatabaseWorkflowActionService()
    with pytest.raises(WorkflowActionDispatchError):
        service.dispatch_workflow_actions(user, button_field, row)

    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None


@pytest.mark.django_db
def test_a_lock_taken_by_a_later_click_is_left_alone(data_fixture):
    """A sequence that outlives the lock's TTL must not delete the key on its
    way out: by then the key can belong to a second click that is still
    running, and removing it would let a third click start alongside it."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")
    lock_key = f"button_dispatch_{button_field.id}_{row.id}"

    def expire_and_retake(sender, **kwargs):
        # Stands in for this click's lock expiring mid-sequence and a second
        # click acquiring the key for itself.
        cache.delete(lock_key)
        cache.add(lock_key, "a-later-click", timeout=30)

    rows_created.connect(expire_and_retake)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        rows_created.disconnect(expire_and_retake)

    assert cache.get(lock_key) == "a-later-click", (
        "The finished sequence deleted a lock it no longer held, so the click "
        "that owns it is now running unprotected."
    )


@pytest.mark.django_db
def test_two_button_fields_on_one_row_do_not_block_each_other(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    first_button = data_fixture.create_button_field(table=table, label="One")
    second_button = data_fixture.create_button_field(table=table, label="Two")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, second_button, table, name_field, "second")

    cache.add(f"button_dispatch_{first_button.id}_{row.id}", True, timeout=30)

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, second_button, row)

    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
def test_an_internal_failure_keeps_its_message_off_the_response(data_fixture):
    """`WorkflowActionDispatchError` renders its message straight into the API
    response, so only messages written for the clicker may become one."""

    from unittest.mock import patch

    from baserow.contrib.database.workflow_actions.handler import (
        DatabaseWorkflowActionHandler,
    )

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")

    with patch.object(
        DatabaseWorkflowActionHandler,
        "dispatch_workflow_action",
        side_effect=ValueError("password=hunter2"),
    ):
        with pytest.raises(ValueError):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    # The lock is still released on the way out of an uncaught failure.
    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None


@pytest.mark.django_db
def test_a_user_without_the_dispatch_permission_is_refused(data_fixture):
    owner = data_fixture.create_user()
    outsider = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, owner)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            outsider, button_field, row
        )

    assert table.get_model().objects.exclude(id=row.id).count() == 0


@pytest.mark.django_db
def test_a_button_with_no_actions_dispatches_nothing(data_fixture):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    results, client_actions = DatabaseWorkflowActionService().dispatch_workflow_actions(
        user, button_field, row
    )

    assert results == []
    assert client_actions == []
    assert cache.get(f"button_dispatch_{button_field.id}_{row.id}") is None


@pytest.mark.django_db
def test_an_outsider_is_refused_on_a_button_with_no_actions(data_fixture):
    """With no actions there are no per-action checks to run, so an unchecked
    empty sequence would answer an outsider with `[]` instead of refusing,
    telling them the field and row exist."""

    owner = data_fixture.create_user()
    outsider = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, owner)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            outsider, button_field, row
        )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_click_does_not_enter_the_undo_stack(data_fixture):
    # Not `transaction=True`: `ActionHandler.undo` takes a `select_for_update`,
    # which needs an open transaction, so the undo tests all run inside the
    # test's own transaction.
    from baserow.api.sessions import set_untrusted_client_session_id
    from baserow.contrib.database.action.scopes import TableActionScopeType
    from baserow.core.action.handler import ActionHandler

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")
    set_untrusted_client_session_id(user, "session-1")

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], "session-1"
    )
    assert undone == []
    assert table.get_model().objects.exclude(id=row.id).count() == 1


@pytest.mark.django_db
def test_every_action_sees_the_row_as_it_was_at_click_time(data_fixture):
    """ADR 006 section 4: the row provider is a snapshot."""

    from baserow.contrib.database.workflow_actions.models import (
        UpdateRowWorkflowAction,
    )

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    row = model.objects.create(**{f"field_{name_field.id}": "before"})

    # First action overwrites the clicked row's Name.
    update = data_fixture.create_database_workflow_action(
        UpdateRowWorkflowAction, field=button_field
    )
    update_service = update.service.specific
    update_service.table = table
    update_service.row_id = str(row.id)
    update_service.save()
    update_service.field_mappings.create(
        field=name_field, value="'after'", enabled=True
    )

    # Second action copies the clicked row's Name into a new row. If the
    # provider re-read the row it would copy 'after'.
    copy = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )
    copy_service = copy.service.specific
    copy_service.table = table
    copy_service.save()
    copy_service.field_mappings.create(
        field=name_field, value=f"get('row.field_{name_field.id}')", enabled=True
    )

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    row.refresh_from_db()
    assert getattr(row, f"field_{name_field.id}") == "after"
    created = model.objects.exclude(id=row.id).get()
    assert getattr(created, f"field_{name_field.id}") == "before", (
        "The second action must see the row as it was at click time, not as the "
        "first action left it (ADR 006 section 4)."
    )


@pytest.mark.django_db
def test_open_url_between_row_actions_is_skipped_and_returned(data_fixture):
    """`open_url` is frontend-only: the server must skip it and hand it back
    rather than dispatch it, without disturbing the row actions around it."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    _create_row_action(data_fixture, button_field, table, name_field, "first")
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    delete = data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field
    )
    service = delete.service.specific
    service.table = table
    service.row_id = "get('row.id')"
    service.save()

    results, client_actions = DatabaseWorkflowActionService().dispatch_workflow_actions(
        user, button_field, row
    )

    assert [a.get_type().type for a, _ in results] == ["create_row", "delete_row"]
    assert [a.get_type().type for a in client_actions] == ["open_url"]


@pytest.mark.django_db
def test_a_click_can_delete_several_rows_at_once(data_fixture):
    """The delete row action accepts an array of ids. The service's own tests
    cover that with an integration behind it; this pins the same behaviour on
    the click path, which runs as the actor with no integration at all."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    clicked = model.objects.create()
    first = model.objects.create(**{f"field_{name_field.id}": "first"})
    second = model.objects.create(**{f"field_{name_field.id}": "second"})
    survivor = model.objects.create(**{f"field_{name_field.id}": "survivor"})

    delete = data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field
    )
    service = delete.service.specific
    service.table = table
    service.row_id = f"'[{first.id}, {second.id}]'"
    service.save()

    DatabaseWorkflowActionService().dispatch_workflow_actions(
        user, button_field, clicked
    )

    assert model.objects.filter(id__in=[first.id, second.id]).exists() is False
    # Neither the untargeted row nor the clicked row itself is touched.
    assert model.objects.filter(id=survivor.id).exists() is True
    assert model.objects.filter(id=clicked.id).exists() is True


@pytest.mark.django_db
def test_a_failing_row_action_means_no_client_actions(data_fixture):
    """A server-side failure re-raises before the client actions are ever
    handed back, so the browser never runs an `open_url` whose preceding
    server action failed."""

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    # A delete-row action with no table configured fails at dispatch.
    data_fixture.create_database_workflow_action(
        DeleteRowWorkflowAction, field=button_field
    )
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    with pytest.raises(WorkflowActionDispatchError):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )


@pytest.mark.django_db
def test_a_button_with_only_an_open_url_does_not_take_the_lock(data_fixture):
    """No server actions means nothing to serialise, so the lock is never
    taken and a second click on a URL-only button is not rejected.

    Asserting the key is absent afterwards would not prove that, since it is
    released in a `finally` either way. Hence seeding the key first and
    asserting the dispatch still succeeds."""

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    cache.add(f"button_dispatch_{button_field.id}_{row.id}", True, timeout=30)

    results, client_actions = DatabaseWorkflowActionService().dispatch_workflow_actions(
        user, button_field, row
    )

    assert results == []
    assert len(client_actions) == 1
