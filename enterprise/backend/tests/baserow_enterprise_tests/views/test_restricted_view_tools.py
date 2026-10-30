import pytest
from baserow_enterprise_tests.assistant.utils import make_test_ctx

from baserow.contrib.database.tools import rows, tables
from baserow.contrib.database.views.models import View
from baserow.core.exceptions import PermissionDenied
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.tools.database import helpers
from baserow_enterprise.assistant.tools.database.tools import list_rows, load_row_tools
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


@pytest.fixture
def restricted_view_member(enable_enterprise, enterprise_data_fixture):
    """
    A member whose only role is on a restricted view. The table is listed to them,
    but REST refuses its rows and fields.
    """

    admin = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin, members=[member])
    table = enterprise_data_fixture.create_database_table(
        database=enterprise_data_fixture.create_database_application(
            workspace=workspace
        )
    )
    field = enterprise_data_fixture.create_text_field(
        table=table, name="Salary", primary=True
    )
    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(
        member, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=workspace
    )
    roles.assign_role(
        member,
        workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=View.objects.get(id=view.id),
    )
    row = table.get_model().objects.create(**{field.db_column: "100"})
    return ToolContext(user=member, workspace=workspace), admin, table, row


@pytest.mark.django_db
def test_a_table_reached_through_a_view_is_listed_without_its_fields(
    restricted_view_member,
):
    ctx, _, table, _ = restricted_view_member

    assert [listed["id"] for listed in tables.list_tables(ctx)] == [table.id]
    assert tables.get_table_schema(ctx, [table.id]) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(
            lambda ctx, table, row: rows.list_table_rows(ctx, table.id), id="list"
        ),
        # An unknown field name would otherwise answer with the table's fields.
        pytest.param(
            lambda ctx, table, row: rows.create_rows(ctx, table.id, [{"Bonus": 1}]),
            id="create",
        ),
        pytest.param(
            lambda ctx, table, row: rows.update_rows(
                ctx, table.id, [rows.RowUpdate(id=row.id, Bonus=1)]
            ),
            id="update",
        ),
        pytest.param(
            lambda ctx, table, row: rows.delete_rows(ctx, table.id, [row.id]),
            id="delete",
        ),
    ],
)
def test_row_tools_refuse_a_table_reached_through_a_view(restricted_view_member, call):
    ctx, _, table, row = restricted_view_member

    with pytest.raises(PermissionDenied):
        call(ctx, table, row)


@pytest.mark.django_db
def test_kuma_refuses_rows_of_a_table_reached_through_a_view(restricted_view_member):
    ctx, _, table, _ = restricted_view_member
    kuma_ctx = make_test_ctx(ctx.user, ctx.workspace)

    with pytest.raises(PermissionDenied):
        list_rows(kuma_ctx, table.id, 0, 20, None, thought="Read rows")
    with pytest.raises(PermissionDenied):
        load_row_tools(
            kuma_ctx, [table.id], ["create", "update", "delete"], thought="Edit rows"
        )
    assert kuma_ctx.deps.dynamic_tools == []


@pytest.mark.django_db
def test_kuma_formulas_leave_out_tables_reached_through_a_view(
    restricted_view_member,
):
    ctx, admin, table, _ = restricted_view_member

    def readable(user):
        return helpers.readable_database_tables(user, ctx.workspace, table.database_id)

    assert readable(admin) == [table]
    assert readable(ctx.user) == []
