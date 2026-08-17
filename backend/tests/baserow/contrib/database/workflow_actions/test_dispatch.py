from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.core.cache import cache

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.signals import rows_created
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
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
        LocalBaserowCreateRowWorkflowAction, field=button_field
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
        LocalBaserowDeleteRowWorkflowAction, field=button_field
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
        LocalBaserowUpdateRowWorkflowAction,
    )

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Approve")
    model = table.get_model()
    row = model.objects.create(**{f"field_{name_field.id}": "pending"})
    other_row = model.objects.create(**{f"field_{name_field.id}": "untouched"})

    action = data_fixture.create_database_workflow_action(
        LocalBaserowUpdateRowWorkflowAction, field=button_field
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
        LocalBaserowDeleteRowWorkflowAction, field=button_field
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
def test_the_lock_is_released_without_a_separate_delete(data_fixture):
    """The test above covers a lock lost well before the release. The window it
    cannot reach is the one inside the release itself: reading the key, then
    losing it to a later click, then deleting what is no longer this click's.
    Closed only by checking ownership and removing the key in one step, so the
    release must not reach for `delete` at all."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _create_row_action(data_fixture, button_field, table, name_field, "first")
    lock_key = f"button_dispatch_{button_field.id}_{row.id}"

    deleted_keys = []
    real_delete = cache.delete

    def record_delete(key, *args, **kwargs):
        deleted_keys.append(key)
        return real_delete(key, *args, **kwargs)

    with patch.object(cache, "delete", side_effect=record_delete):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert lock_key not in deleted_keys, (
        "The lock was released with a delete of its own, so a TTL that runs out "
        "between the ownership check and the delete takes a later click's lock "
        "with it."
    )
    # Released all the same, or the next click on this row would be refused.
    assert cache.get(lock_key) is None


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
def test_every_action_sees_what_the_actions_before_it_did(data_fixture):
    """ADR 006 section 4: the row provider re-reads per action."""

    from baserow.contrib.database.workflow_actions.models import (
        LocalBaserowUpdateRowWorkflowAction,
    )

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    row = model.objects.create(**{f"field_{name_field.id}": "before"})

    # First action overwrites the clicked row's Name.
    update = data_fixture.create_database_workflow_action(
        LocalBaserowUpdateRowWorkflowAction, field=button_field
    )
    update_service = update.service.specific
    update_service.table = table
    update_service.row_id = str(row.id)
    update_service.save()
    update_service.field_mappings.create(
        field=name_field, value="'after'", enabled=True
    )

    # Second action copies the clicked row's Name into a new row. If the
    # provider held a click-time snapshot it would copy 'before'.
    copy = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
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
    assert getattr(created, f"field_{name_field.id}") == "after", (
        "The second action must see the row as the first action left it, not "
        "as it was at click time (ADR 006 section 4)."
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
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )
    service = delete.service.specific
    service.table = table
    service.row_id = "get('row.id')"
    service.save()

    results, client_actions = DatabaseWorkflowActionService().dispatch_workflow_actions(
        user, button_field, row
    )

    assert [a.get_type().type for a, _ in results] == [
        "local_baserow_create_row",
        "local_baserow_delete_row",
    ]
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
        LocalBaserowDeleteRowWorkflowAction, field=button_field
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
        LocalBaserowDeleteRowWorkflowAction, field=button_field
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


@pytest.mark.django_db
def test_a_service_carrying_an_integration_does_not_run_as_its_user(data_fixture):
    """An integration's `authorized_user` outranks the dispatch actor. The row
    count either side proves the refusal left the table alone."""

    user = data_fixture.create_user()
    victim = data_fixture.create_user()
    victim_integration = data_fixture.create_local_baserow_integration(
        user=victim, authorized_user=victim
    )
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _create_row_action(data_fixture, button_field, table, name_field, "made")
    service = action.service.specific
    service.integration = victim_integration
    service.save()
    rows_before = table.get_model().objects.count()

    with pytest.raises(WorkflowActionDispatchError):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert table.get_model().objects.count() == rows_before


@pytest.mark.django_db
def test_a_multiple_select_is_read_as_fresh_as_the_text_beside_it(data_fixture):
    """The bug reported on the phase 2a review: a sequence copied the clicked
    row's text as it was at click time, but its multiple select as an earlier
    action had left it. Values held through a related manager are fetched when
    they are read, so they were never part of the snapshot the rest of the row
    was. Both must read the same way, whichever way that is."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    select_field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    option_a = data_fixture.create_select_option(field=select_field, value="a")
    option_b = data_fixture.create_select_option(field=select_field, value="b")
    button_field = data_fixture.create_button_field(table=table, label="Go")

    model = table.get_model()
    name_column = f"field_{name_field.id}"
    tags_column = f"field_{select_field.id}"
    row = model.objects.create(**{name_column: "before"})
    getattr(row, tags_column).set([option_a.id])

    # The first action changes the clicked row's name and tags. No runtime
    # formula builds a list, so a multiple select cannot be written by a field
    # mapping: the change rides on the first action's signal instead.
    def change_the_clicked_row(sender, **kwargs):
        changed = model.objects.get(id=row.id)
        setattr(changed, name_column, "after")
        changed.save()
        getattr(changed, tags_column).set([option_b.id])

    # It reads the name as well, so a provider that read the row once for the
    # whole click would answer the second action from this action's read.
    first = _create_row_action(data_fixture, button_field, table, name_field, "unused")
    first_mapping = first.service.specific.field_mappings.get()
    first_mapping.value = f"get('row.{name_column}')"
    first_mapping.save()

    # The second action copies both of the clicked row's values into a new row.
    copy = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    copy_service = copy.service.specific
    copy_service.table = table
    copy_service.save()
    copy_service.field_mappings.create(
        field=name_field, value=f"get('row.{name_column}')", enabled=True
    )
    copy_service.field_mappings.create(
        field=select_field, value=f"get('row.{tags_column}')", enabled=True
    )

    rows_created.connect(change_the_clicked_row)
    try:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    finally:
        rows_created.disconnect(change_the_clicked_row)

    copied = model.objects.exclude(id=row.id).order_by("id").last()
    copied_name = getattr(copied, name_column)
    copied_tags = [option.id for option in getattr(copied, tags_column).all()]

    assert (copied_name, copied_tags) == ("after", [option_b.id]), (
        "The text and the multiple select must be read at the same moment. "
        f"Got name={copied_name!r} and tags={copied_tags!r}: one of them is a "
        "click-time snapshot and the other is not (ADR 006 section 4)."
    )


@pytest.mark.django_db
def test_reading_the_clicked_row_after_it_was_deleted_fails_the_action(data_fixture):
    """ADR 006 section 4: resolving to nothing would let the action write
    blanks, so it fails and the sequence stops instead."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    row = model.objects.create(**{f"field_{name_field.id}": "doomed"})

    # First action deletes the clicked row.
    delete = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )
    delete_service = delete.service.specific
    delete_service.table = table
    delete_service.row_id = "get('row.id')"
    delete_service.save()

    # Second action tries to read it afterwards.
    copy = _create_row_action(data_fixture, button_field, table, name_field, "unused")
    mapping = copy.service.specific.field_mappings.get()
    mapping.value = f"get('row.field_{name_field.id}')"
    mapping.save()

    with pytest.raises(WorkflowActionDispatchError) as exc:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert exc.value.workflow_action_id == copy.id
    # The delete stands: completed actions are never rolled back.
    assert model.objects.count() == 0


@pytest.mark.django_db
def test_a_password_field_cannot_be_read_into_another_row(data_fixture):
    """The stored value is the hash. Every other surface masks it, so the row
    provider must not be the one way to copy it somewhere readable."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    password_field = data_fixture.create_password_field(table=table, name="Secret")
    button_field = data_fixture.create_button_field(table=table, label="Go")

    model = table.get_model()
    hashed = make_password("hunter2")
    row = model.objects.create(**{f"field_{password_field.id}": hashed})

    copy = _create_row_action(data_fixture, button_field, table, name_field, "unused")
    mapping = copy.service.specific.field_mappings.get()
    mapping.value = f"get('row.field_{password_field.id}')"
    mapping.save()

    with pytest.raises(WorkflowActionDispatchError) as exc:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert exc.value.workflow_action_id == copy.id
    assert hashed not in str(exc.value), "The refusal must not carry the hash."
    written = [getattr(r, f"field_{name_field.id}") for r in model.objects.all()]
    assert hashed not in written


@pytest.mark.django_db
def test_a_mapping_left_on_a_trashed_field_fails_rather_than_writing_without_it(
    data_fixture,
):
    """ADR 006 section 8: the reference is kept and the button asks to be
    reconfigured. Dropping the mapping would write a row missing the value the
    action was configured to put there."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    doomed_field = data_fixture.create_text_field(table=table, name="Doomed")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    row = model.objects.create()

    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value="'kept'", enabled=True)
    service.field_mappings.create(field=doomed_field, value="'gone'", enabled=True)

    FieldHandler().delete_field(user, doomed_field)
    rows_before = model.objects.count()

    with pytest.raises(WorkflowActionDispatchError) as exc:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert exc.value.workflow_action_id == action.id
    assert model.objects.count() == rows_before
    # The mapping is still there, so restoring the field heals it.
    assert service.field_mappings.count() == 2


@pytest.mark.django_db
def test_a_disabled_mapping_on_a_trashed_field_does_not_stop_the_click(data_fixture):
    """A disabled mapping writes nothing, so a trashed field behind one is not
    something the clicker has to reconfigure."""

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    doomed_field = data_fixture.create_text_field(table=table, name="Doomed")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    row = model.objects.create()

    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value="'kept'", enabled=True)
    service.field_mappings.create(field=doomed_field, value="'gone'", enabled=False)

    FieldHandler().delete_field(user, doomed_field)

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    created = model.objects.exclude(id=row.id).get()
    assert getattr(created, f"field_{name_field.id}") == "kept"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_save_restores_the_field_but_not_its_actions(data_fixture):
    """ADR 006 section 8: the actions are not undoable yet, while the field
    around them is. This pins that half state so it is a decision rather than a
    surprise, and fails when undo is implemented, which is when the ADR needs
    revisiting."""

    from baserow.api.sessions import set_untrusted_client_session_id
    from baserow.contrib.database.action.scopes import TableActionScopeType
    from baserow.contrib.database.fields.actions import UpdateFieldActionType
    from baserow.core.action.handler import ActionHandler

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Before")
    set_untrusted_client_session_id(user, "session-1")

    # A save changes the label and adds an action, the way the editor does.
    UpdateFieldActionType.do(user, button_field, new_type_name="button", label="After")
    DatabaseWorkflowActionService().create_workflow_action(
        user, database_workflow_action_type_registry.get("open_url"), button_field
    )

    ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], "session-1"
    )

    button_field.refresh_from_db()
    assert button_field.label == "Before"
    assert button_field.workflow_actions.count() == 1
