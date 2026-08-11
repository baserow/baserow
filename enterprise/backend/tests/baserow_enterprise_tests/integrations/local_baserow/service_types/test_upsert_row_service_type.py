from django.test.utils import override_settings

import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


def _table_with_a_protected_field(enterprise_data_fixture, workspace, author, admin):
    """A table whose "Protected" field only an admin may write values to."""

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = TableHandler().create_table_and_fields(
        user=author,
        database=database,
        name=enterprise_data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
            ("Protected", "text", {}),
        ],
    )

    enterprise_data_fixture.enable_enterprise()
    RoleAssignmentHandler().assign_role(
        subject=admin,
        workspace=workspace,
        role=Role.objects.get(uid="ADMIN"),
        scope=database,
    )

    protected_field = table.field_set.get(name="Protected")
    FieldPermissionsHandler.update_field_permissions(
        admin, protected_field.specific, "ADMIN"
    )

    return table, table.field_set.get(name="Ingredient"), protected_field


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_local_baserow_upsert_row_service_dispatch_data_with_protected_table_field(
    enterprise_data_fixture, synced_roles
):
    """The builder's documented behaviour: a field the integration's user cannot
    write is skipped and the rest of the row is written. Nothing about the
    button field's stricter rule (ADR 006 section 5) may change this."""

    builder_user = enterprise_data_fixture.create_user()
    admin_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[builder_user, admin_user]
    )

    builder = enterprise_data_fixture.create_builder_application(workspace=workspace)
    integration = enterprise_data_fixture.create_local_baserow_integration(
        application=builder, user=builder_user
    )
    table, writable_field, protected_field = _table_with_a_protected_field(
        enterprise_data_fixture, workspace, builder_user, admin_user
    )
    RoleAssignmentHandler().assign_role(
        subject=builder_user,
        workspace=workspace,
        role=Role.objects.get(uid="BUILDER"),
        scope=table.database,
    )

    service = enterprise_data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )
    service_type = service.get_type()
    service.field_mappings.create(field=writable_field, value="'Cheese'")
    service.field_mappings.create(field=protected_field, value="'New data'")

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    dispatch_data = service_type.dispatch_data(
        service, dispatch_values, dispatch_context
    )

    row = dispatch_data["data"]
    row.refresh_from_db()

    assert getattr(row, writable_field.db_column) == "Cheese"
    assert getattr(row, protected_field.db_column) is None, (
        "The builder skips the field its integration's user cannot write and "
        "writes the rest of the row. ADR 006 section 5's stricter rule belongs "
        "to the button field's dispatch context and must not reach here."
    )


def _button_writing(enterprise_data_fixture, table, fields):
    """A button field on `table` whose single action writes `fields`."""

    button_field = enterprise_data_fixture.create_button_field(
        table=table, label="Go", create_field=True
    )
    action = enterprise_data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    for field in fields:
        service.field_mappings.create(field=field, value="'Cheese'", enabled=True)

    return button_field


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_a_click_writing_only_writable_fields_succeeds(
    enterprise_data_fixture, synced_roles
):
    admin_user = enterprise_data_fixture.create_user()
    clicker = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[admin_user, clicker])

    table, writable_field, _ = _table_with_a_protected_field(
        enterprise_data_fixture, workspace, admin_user, admin_user
    )
    RoleAssignmentHandler().assign_role(
        subject=clicker,
        workspace=workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=table.database,
    )

    button_field = _button_writing(enterprise_data_fixture, table, [writable_field])
    row = table.get_model().objects.create()

    DatabaseWorkflowActionService().dispatch_workflow_actions(
        clicker, button_field, row
    )

    created = table.get_model().objects.exclude(id=row.id).get()
    assert getattr(created, writable_field.db_column) == "Cheese"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_a_click_writing_an_unwritable_field_fails(
    enterprise_data_fixture, synced_roles
):
    """ADR 006 section 5: the click fails rather than writing the row without
    the field the clicker cannot write."""

    admin_user = enterprise_data_fixture.create_user()
    clicker = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(users=[admin_user, clicker])

    table, writable_field, protected_field = _table_with_a_protected_field(
        enterprise_data_fixture, workspace, admin_user, admin_user
    )
    RoleAssignmentHandler().assign_role(
        subject=clicker,
        workspace=workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=table.database,
    )

    button_field = _button_writing(
        enterprise_data_fixture, table, [writable_field, protected_field]
    )
    row = table.get_model().objects.create()

    # `WorkflowActionDispatchError` is what the API turns into
    # ERROR_WORKFLOW_ACTION_DISPATCH_FAILED and the clicker's error toast. Any
    # other exception here means the clicker gets a 500 instead.
    with pytest.raises(WorkflowActionDispatchError) as exc:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            clicker, button_field, row
        )

    # The clicker may have no access to the target table at all, so the
    # refusal says what happened without naming the fields.
    assert exc.value.message == (
        "You don't have permission to write to the fields this action changes."
    )
    assert protected_field.name not in exc.value.message

    # Not even the field the clicker could write is left behind.
    assert table.get_model().objects.exclude(id=row.id).count() == 0
