import pytest

from baserow.contrib.database.views.models import View
from baserow.core.models import Agent as Identity
from baserow.core.services.registries import service_type_registry
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


@pytest.mark.django_db
def test_rows_triggers_need_a_role_that_lists_the_rows_of_the_table(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    workspace = enterprise_data_fixture.create_workspace(
        user=enterprise_data_fixture.create_user()
    )
    database = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Sales"
    )
    orders, invoices, salaries = (
        enterprise_data_fixture.create_database_table(database=database, name=name)
        for name in ("Orders", "Invoices", "Salaries")
    )
    restricted = enterprise_data_fixture.create_grid_view(
        table=invoices, ownership_type=RestrictedViewOwnershipType.type
    )
    identity = Identity.objects.create(
        workspace=workspace, name="Reader", role_uid="NO_ACCESS"
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(identity, workspace, Role.objects.get(uid="VIEWER"), scope=orders)
    roles.assign_role(
        identity,
        workspace,
        Role.objects.get(uid="EDITOR"),
        scope=View.objects.get(id=restricted.id),
    )
    service_type = service_type_registry.get("local_baserow_rows_created")

    choices = service_type.get_form_choices(identity, workspace)
    readable = {
        table.name: service_type.can_subject_read(
            enterprise_data_fixture.create_local_baserow_rows_created_service(
                table=table, integration=None
            ),
            identity,
            workspace,
        )
        for table in (orders, invoices, salaries)
    }

    assert [
        (database["name"], [table["name"] for table in database["tables"]])
        for database in choices["databases"]
    ] == [("Sales", ["Orders"])]
    assert readable == {"Orders": True, "Invoices": False, "Salaries": False}
