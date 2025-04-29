from django.test.utils import override_settings

import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.field_permissions.handler import FieldPermissionsHandler
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_local_baserow_upsert_row_service_dispatch_data_with_protected_table_field(
    enterprise_data_fixture, synced_roles
):
    builder_user = enterprise_data_fixture.create_user()
    admin_user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(
        users=[builder_user, admin_user]
    )

    builder = enterprise_data_fixture.create_builder_application(workspace=workspace)
    integration = enterprise_data_fixture.create_local_baserow_integration(
        application=builder, user=builder_user
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = TableHandler().create_table_and_fields(
        user=builder_user,
        database=database,
        name=enterprise_data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
            ("Protected", "text", {}),
        ],
    )

    enterprise_data_fixture.enable_enterprise()
    RoleAssignmentHandler().assign_role(
        subject=admin_user,
        workspace=database.workspace,
        role=Role.objects.get(uid="ADMIN"),
        scope=database,
    )
    RoleAssignmentHandler().assign_role(
        subject=builder_user,
        workspace=database.workspace,
        role=Role.objects.get(uid="BUILDER"),
        scope=database,
    )

    writable_field = table.field_set.get(name="Ingredient")
    protected_field = table.field_set.get(name="Protected")

    FieldPermissionsHandler.update_field_permissions(
        admin_user, protected_field.specific, "ADMIN"
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

    assert getattr(dispatch_data["data"], writable_field.db_column) == "Cheese"
