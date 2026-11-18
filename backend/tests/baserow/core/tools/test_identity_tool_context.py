import pytest

from baserow.api.sessions import set_untrusted_client_session_id
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.tools.nodes import (
    add_nodes,
    delete_nodes,
    list_nodes,
    update_nodes,
)
from baserow.contrib.automation.tools.types import (
    ActionNodeCreate,
    NodeUpdate,
    WorkflowCreate,
)
from baserow.contrib.automation.tools.workflows import create_workflows, list_workflows
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    DeleteRowsActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.table.actions import CreateTableActionType
from baserow.contrib.database.tools.fields import (
    FieldItemCreate,
    FieldItemUpdate,
    create_fields,
    delete_fields,
    update_fields,
)
from baserow.contrib.database.tools.tables import (
    TableItemCreate,
    create_tables,
    get_table_schema,
    list_tables,
)
from baserow.contrib.database.tools.views import (
    FormFieldOption,
    ViewFilterItemCreate,
    ViewFiltersArgs,
    ViewItemCreate,
    create_view_filters,
    create_views,
    list_views,
)
from baserow.contrib.database.views.models import (
    FormView,
    FormViewFieldOptions,
    ViewFilter,
)
from baserow.core.action.models import Action
from baserow.core.action.signals import action_done
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.identities.service import IdentityService
from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import list_applications


@pytest.fixture(params=["user", "identity"])
def execution_context(data_fixture, request):
    owner = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=owner)
    user = (
        owner
        if request.param == "user"
        else data_fixture.create_identity(workspace=workspace)
    )
    # Even an identity carrying a client session must not get interactive undo.
    set_untrusted_client_session_id(user, "execution-test-session")
    return ToolContext(user=user, workspace=workspace), request.param


def assert_execution_attribution(ctx, kind, send_action, expected_types):
    calls = send_action.call_args_list
    assert {call.kwargs["action_type"].type for call in calls} == expected_types
    assert all(call.kwargs["user"] == ctx.user for call in calls)
    actions = Action.objects.filter(user=ctx.user)
    if kind == "identity":
        assert not actions.exists()
    else:
        assert set(actions.values_list("type", flat=True)) == expected_types
        assert set(actions.values_list("session", flat=True)) == {
            "execution-test-session"
        }


@pytest.mark.django_db
def test_identity_tools_use_shared_actions_without_interactive_undo(
    data_fixture, mocker
):
    database = data_fixture.create_database_application()
    identity = data_fixture.create_identity(workspace=database.workspace)
    ctx = ToolContext(user=identity, workspace=database.workspace)
    send_action = mocker.spy(action_done, "send")

    applications = list_applications(ctx)
    result = create_tables(
        ctx,
        database.id,
        [
            TableItemCreate(
                name="Tasks",
                primary_field_name="Task",
                fields=[FieldItemCreate(name="Notes", type="text")],
            )
        ],
    )

    table = database.table_set.get(name="Tasks")
    assert [app["id"] for app in applications["applications"]] == [database.id]
    assert result["created_tables"][0]["id"] == table.id
    assert set(table.field_set.values_list("name", flat=True)) == {"Task", "Notes"}
    assert not Action.objects.filter(user=identity).exists()
    assert any(
        call.kwargs["sender"] is CreateTableActionType
        and call.kwargs["user"] == identity
        for call in send_action.call_args_list
    )


@pytest.mark.django_db
@pytest.mark.parametrize("denial", ["disabled", "trashed", "other_workspace"])
def test_identity_tools_recheck_execution_permissions(data_fixture, denial):
    database = data_fixture.create_database_application()
    identity = data_fixture.create_identity(
        workspace=(
            data_fixture.create_workspace()
            if denial == "other_workspace"
            else database.workspace
        ),
        is_active=denial != "disabled",
        trashed=denial == "trashed",
    )
    ctx = ToolContext(user=identity, workspace=database.workspace)

    # Tools report a database they may not use as missing, never as forbidden.
    with pytest.raises(ApplicationDoesNotExist):
        create_tables(
            ctx,
            database.id,
            [TableItemCreate(name="Tasks", primary_field_name="Task", fields=[])],
        )

    assert not database.table_set.exists()
    assert not Action.objects.filter(user=identity).exists()


@pytest.mark.django_db
def test_tool_field_lifecycle_preserves_execution_attribution(
    data_fixture, execution_context, mocker
):
    ctx, kind = execution_context
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(table=table, primary=True, name="Name")
    send_action = mocker.spy(action_done, "send")

    created = create_fields(ctx, table.id, [FieldItemCreate(name="Notes", type="text")])
    field = table.field_set.get(name="Notes")
    assert created["created_fields"][0]["id"] == field.id
    updated = update_fields(ctx, [FieldItemUpdate(field_id=field.id, name="Details")])
    field.refresh_from_db()
    assert updated["changed"] is True
    assert field.name == "Details"
    assert {item["id"] for item in list_tables(ctx, database.id)} == {table.id}
    schema = get_table_schema(ctx, [table.id])
    assert {item["name"] for item in schema[0]["fields"]} == {"Name", "Details"}

    assert delete_fields(ctx, [field.id])["deleted_field_ids"] == [field.id]
    assert Field.objects_and_trash.get(id=field.id).trashed
    assert list(table.field_set.values_list("id", flat=True)) == [primary.id]
    assert_execution_attribution(
        ctx, kind, send_action, {"create_field", "update_field", "delete_field"}
    )


@pytest.mark.django_db
def test_tool_lookup_dependencies_preserve_execution_attribution(
    data_fixture, execution_context, mocker
):
    ctx, kind = execution_context
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    orders = data_fixture.create_database_table(database=database, name="Orders")
    catalog = data_fixture.create_database_table(database=database, name="Catalog")
    data_fixture.create_text_field(table=orders, primary=True, name="Name")
    data_fixture.create_text_field(table=catalog, primary=True, name="Product")
    price = data_fixture.create_number_field(table=catalog, name="Price")
    send_action = mocker.spy(action_done, "send")

    created = create_fields(
        ctx,
        orders.id,
        [
            FieldItemCreate(
                name="Prices",
                type="lookup",
                linked_table="Catalog",
                target_field="Price",
            )
        ],
    )
    link_item, lookup_item = created["created_fields"]
    link = orders.field_set.get(id=link_item["id"]).specific
    lookup = orders.field_set.get(id=lookup_item["id"]).specific
    assert link.link_row_table_id == catalog.id
    assert link.link_row_related_field.table_id == catalog.id
    assert lookup.through_field_id == link.id
    assert lookup.target_field_id == price.id

    update_fields(ctx, [FieldItemUpdate(field_id=price.id, name="Unit price")])
    lookup.refresh_from_db()
    assert lookup.target_field_name == "Unit price"
    assert not lookup.error
    assert delete_fields(ctx, [lookup.id])["deleted_field_ids"] == [lookup.id]
    assert Field.objects_and_trash.get(id=lookup.id).trashed
    assert orders.field_set.filter(id=link.id).exists()
    assert_execution_attribution(
        ctx, kind, send_action, {"create_field", "update_field", "delete_field"}
    )


@pytest.mark.django_db
def test_tool_view_filters_and_form_options_preserve_execution_attribution(
    data_fixture, execution_context, mocker
):
    ctx, kind = execution_context
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, primary=True, name="Name")
    amount = data_fixture.create_number_field(table=table, name="Amount")
    send_action = mocker.spy(action_done, "send")

    created = create_views(
        ctx,
        table.id,
        [
            ViewItemCreate(name="Large orders", type="grid"),
            ViewItemCreate(
                name="Order form",
                type="form",
                title="Place an order",
                receive_notification_on_submit=True,
                field_options=[
                    FormFieldOption(
                        field_id=name.id,
                        name="Your name",
                        description="Order contact",
                        required=True,
                        order=0,
                    )
                ],
            ),
        ],
    )
    grid, form_item = created["created_views"]
    form = FormView.objects.get(id=form_item["id"])
    option = FormViewFieldOptions.objects.get(form_view=form, field=name)
    assert form.title == "Place an order"
    assert (option.enabled, option.required, option.name) == (True, True, "Your name")
    assert not FormViewFieldOptions.objects.filter(
        form_view=form, field=amount, enabled=True
    ).exists()
    assert list(form.users_to_notify_on_submit.all()) == (
        [ctx.user] if kind == "user" else []
    )

    filtered = create_view_filters(
        ctx,
        [
            ViewFiltersArgs(
                view_id=grid["id"],
                filters=[
                    ViewFilterItemCreate(
                        field_id=amount.id,
                        type="number",
                        operator="higher_than",
                        value=10,
                    )
                ],
            )
        ],
    )
    assert filtered["changed"] is True
    view_filter = ViewFilter.objects.get(view_id=grid["id"])
    assert (view_filter.field_id, view_filter.type, view_filter.value) == (
        amount.id,
        "higher_than",
        "10",
    )
    assert {view["id"] for view in list_views(ctx, table.id)["views"]} == {
        grid["id"],
        form.id,
    }
    assert_execution_attribution(
        ctx,
        kind,
        send_action,
        {"create_view", "update_view_field_options", "create_view_filter"},
    )


@pytest.mark.django_db
def test_tool_automation_lifecycle_preserves_execution_attribution(
    data_fixture, execution_context, mocker
):
    ctx, kind = execution_context
    automation = data_fixture.create_automation_application(workspace=ctx.workspace)
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, primary=True, name="Name")
    send_action = mocker.spy(action_done, "send")

    created = create_workflows(
        ctx,
        automation.id,
        [
            WorkflowCreate(
                name="Orders",
                trigger={
                    "ref": "trigger",
                    "type": "rows_created",
                    "rows_triggers_settings": {"table_id": table.id},
                },
                nodes=[],
            )
        ],
    )
    workflow = AutomationWorkflow.objects.get(id=created["created_workflows"][0]["id"])
    trigger = workflow.get_trigger()
    added = add_nodes(
        ctx,
        workflow.id,
        [
            ActionNodeCreate(
                ref="store",
                type="create_row",
                previous_node_ref=str(trigger.id),
                label="Store order",
                table_id=table.id,
                values=[{"field_id": name.id, "value": "Received"}],
            )
        ],
    )
    node = AutomationNode.objects.get(id=added["created_nodes"][0]["id"])
    workflow.refresh_from_db()
    assert workflow.graph[str(trigger.id)]["next"][""] == [node.id]
    assert node.service.specific.field_mappings.get(field=name).value["formula"] == (
        "'Received'"
    )
    updated = update_nodes(
        ctx,
        workflow.id,
        [NodeUpdate(node_id=node.id, label="Save order")],
    )
    node.refresh_from_db()
    assert node.label == "Save order"
    assert updated["updated_nodes"][0]["node_id"] == node.id
    assert {item["id"] for item in list_nodes(ctx, workflow.id)["nodes"]} == {
        trigger.id,
        node.id,
    }
    listed = list_workflows(ctx, automation.id)["automations"][0]["workflows"]
    assert [item["id"] for item in listed] == [workflow.id]

    assert delete_nodes(ctx, [node.id])["deleted_node_ids"] == [node.id]
    assert not AutomationNode.objects.filter(id=node.id).exists()
    workflow.refresh_from_db()
    assert str(node.id) not in workflow.graph
    assert [item["id"] for item in list_nodes(ctx, workflow.id)["nodes"]] == [
        trigger.id
    ]
    assert_execution_attribution(
        ctx,
        kind,
        send_action,
        {
            "create_automation_workflow",
            "create_automation_node",
            "update_automation_node",
            "delete_automation_node",
        },
    )


@pytest.mark.django_db
def test_table_import_preserves_execution_attribution(
    data_fixture, execution_context, mocker
):
    ctx, kind = execution_context
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    send_action = mocker.spy(action_done, "send")

    # Data import is a supported branch of the same action/handler used by
    # create_tables, although the shared tool currently creates empty tables.
    table, errors = CreateTableActionType.do(
        ctx.user,
        database,
        "Orders",
        data=[["Name"], ["First"], ["Second"]],
    )
    assert not errors
    field = table.field_set.get(primary=True)
    rows = table.get_model().objects.order_by("id")
    assert list(rows.values_list(field.db_column, flat=True)) == ["First", "Second"]
    assert {row.created_by_id for row in rows} == {ctx.user.id}
    assert {row.last_modified_by_id for row in rows} == {ctx.user.id}
    assert_execution_attribution(ctx, kind, send_action, {"create_table"})


@pytest.mark.django_db
@pytest.mark.row_history
def test_row_actions_preserve_execution_attribution_after_identity_trash(
    data_fixture, execution_context, mocker
):
    ctx, kind = execution_context
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    model = table.get_model()
    send_action = mocker.spy(action_done, "send")

    # Row mutations currently use separate action/MCP paths, not ToolContext
    # entry points. Exercise their persisted foundation attribution directly.
    (created,) = CreateRowsActionType.do(ctx.user, table, [{field.db_column: "Before"}])
    row = model.objects.get(id=created.id)
    assert getattr(row, field.db_column) == "Before"
    assert row.created_by_id == row.last_modified_by_id == ctx.user.id

    UpdateRowsActionType.do(ctx.user, table, [{"id": row.id, field.db_column: "After"}])
    row.refresh_from_db()
    assert getattr(row, field.db_column) == "After"
    assert row.created_by_id == row.last_modified_by_id == ctx.user.id

    DeleteRowsActionType.do(ctx.user, table, [row.id])
    assert not model.objects.filter(id=row.id).exists()
    retained = model.objects_and_trash.get(id=row.id)
    assert retained.trashed
    assert getattr(retained, field.db_column) == "After"
    assert_execution_attribution(
        ctx, kind, send_action, {"create_rows", "update_rows", "delete_rows"}
    )

    if kind == "identity":
        owner = ctx.workspace.users.get()
        IdentityService().delete_identity(owner, ctx.user)

    retained.refresh_from_db()
    assert retained.created_by == retained.last_modified_by == ctx.user
    history = RowHistory.objects.filter(table=table, row_id=row.id)
    assert set(history.values_list("action_type", flat=True)) == {
        "create_rows",
        "update_rows",
        "delete_rows",
    }
    assert set(history.values_list("actor_id", "actor_name")) == {
        (ctx.user.id, ctx.user.first_name)
    }


@pytest.mark.django_db
@pytest.mark.parametrize("prefetched", [False, True], ids=["plain", "prefetched"])
@pytest.mark.parametrize(
    "revocation",
    [
        "disabled",
        "trashed",
        "pending_deletion",
        "membership_removed",
        "workspace_trashed",
        "deleted",
    ],
)
def test_identity_tools_recheck_a_previously_used_context(
    data_fixture, revocation, prefetched
):
    owner = data_fixture.create_user()
    database = data_fixture.create_database_application(user=owner)
    identity = data_fixture.create_identity(workspace=database.workspace)
    ctx = ToolContext(user=identity, workspace=database.workspace)
    if prefetched:
        ctx.workspace = Workspace.objects.prefetch_related(
            "workspaceuser_set__user__profile"
        ).get(id=ctx.workspace.id)
        memberships = ctx.workspace._prefetched_objects_cache["workspaceuser_set"]

    create_tables(
        ctx,
        database.id,
        [TableItemCreate(name="Before", primary_field_name="Name", fields=[])],
    )
    table_id = database.table_set.get(name="Before").id
    assert list_applications(ctx)["total"] == 1
    assert [table["id"] for table in list_tables(ctx)] == [table_id]
    if prefetched:
        # Another caller sharing this context keeps its own request snapshot.
        assert (
            ctx.workspace._prefetched_objects_cache["workspaceuser_set"] is memberships
        )
    # Revoke through a separately loaded object, leaving the context stale.
    reloaded = type(identity).objects_and_identities.get(id=identity.id)
    if revocation == "disabled":
        reloaded.is_active = False
        reloaded.save(update_fields=["is_active"])
    elif revocation == "trashed":
        IdentityService().delete_identity(owner, reloaded)
    elif revocation == "pending_deletion":
        reloaded.profile.to_be_deleted = True
        reloaded.profile.save(update_fields=["to_be_deleted"])
    elif revocation == "membership_removed":
        WorkspaceUser.objects_and_identities.filter(user=reloaded).delete()
    elif revocation == "workspace_trashed":
        Workspace.objects.filter(id=database.workspace_id).update(trashed=True)
    else:
        reloaded.delete()

    with pytest.raises(ApplicationDoesNotExist):
        create_tables(
            ctx,
            database.id,
            [TableItemCreate(name="After", primary_field_name="Name", fields=[])],
        )
    assert list(database.table_set.values_list("name", flat=True)) == ["Before"]
    assert not Action.objects.filter(user=identity).exists()
    assert list_applications(ctx)["applications"] == []
    assert list_tables(ctx) == []
    assert get_table_schema(ctx, [table_id]) == []


@pytest.mark.django_db
@pytest.mark.parametrize("prefetched", [False, True], ids=["plain", "prefetched"])
@pytest.mark.parametrize("revocation", ["disabled", "pending_deletion"])
def test_user_tools_recheck_a_previously_used_context(
    data_fixture, revocation, prefetched
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    ctx = ToolContext(user=user, workspace=database.workspace)
    if prefetched:
        ctx.workspace = Workspace.objects.prefetch_related(
            "workspaceuser_set__user__profile"
        ).get(id=ctx.workspace.id)
        memberships = ctx.workspace._prefetched_objects_cache["workspaceuser_set"]
    create_tables(
        ctx,
        database.id,
        [TableItemCreate(name="Before", primary_field_name="Name", fields=[])],
    )
    assert list_applications(ctx)["total"] == 1
    if prefetched:
        assert (
            ctx.workspace._prefetched_objects_cache["workspaceuser_set"] is memberships
        )
    previous_actions = Action.objects.filter(user=user).count()
    reloaded = type(user).objects.get(id=user.id)
    if revocation == "disabled":
        reloaded.is_active = False
        reloaded.save(update_fields=["is_active"])
    else:
        reloaded.profile.to_be_deleted = True
        reloaded.profile.save(update_fields=["to_be_deleted"])

    # Tools report a database they may not use as missing, never as forbidden.
    with pytest.raises(ApplicationDoesNotExist):
        create_tables(
            ctx,
            database.id,
            [TableItemCreate(name="After", primary_field_name="Name", fields=[])],
        )
    assert list(database.table_set.values_list("name", flat=True)) == ["Before"]
    assert Action.objects.filter(user=user).count() == previous_actions
    assert list_applications(ctx)["applications"] == []
    assert list_tables(ctx) == []
