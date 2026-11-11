from unittest.mock import Mock

import pytest

from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
)


@pytest.mark.parametrize(
    "path,id_mapping,expected",
    [
        # When path has fewer than 2 elements, return as is
        ([], {}, []),
        (["0"], {}, ["0"]),
        # When field_dbname doesn't start with "field_", return path as is
        (["0", "id"], {}, ["0", "id"]),
        (["0", "foo"], {}, ["0", "foo"]),
        # {rowIndex}.{fieldName} and field not in mapping
        (["0", "field_1"], {}, ["0", "field_1"]),
        # {rowIndex}.{fieldName} and field in mapping
        (["0", "field_1"], {"database_fields": {1: 2}}, ["0", "field_2"]),
        # {rowIndex}.{fieldName}.{fieldValueIndex}.{value} and field not in mapping
        (["0", "field_1", "0", "value"], {}, ["0", "field_1", "0", "value"]),
        # {rowIndex}.{fieldName}.{fieldValueIndex}.{value} and field in mapping
        (
            ["0", "field_1", "0", "value"],
            {"database_fields": {1: 2}},
            ["0", "field_2", "0", "value"],
        ),
    ],
)
def test_local_baserow_rows_signal_service_type_import_path(path, id_mapping, expected):
    assert (
        LocalBaserowRowsCreatedTriggerServiceType().import_path(path, id_mapping)
        == expected
    )


@pytest.mark.django_db
def test_local_baserow_rows_signal_service_type_skips_table_of_another_workspace(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    workspace = table.database.workspace
    same_workspace = data_fixture.create_local_baserow_rows_created_service(
        table=table,
        integration=data_fixture.create_local_baserow_integration(
            application=data_fixture.create_automation_application(workspace=workspace),
            authorized_user=user,
        ),
    )
    without_integration = data_fixture.create_local_baserow_rows_created_service(
        table=table, integration=None
    )
    data_fixture.create_local_baserow_rows_created_service(
        table=table,
        integration=data_fixture.create_local_baserow_integration(authorized_user=user),
    )

    service_type = LocalBaserowRowsCreatedTriggerServiceType()
    service_type.on_event = Mock()
    service_type._handle_signal(
        None, user, rows=[], table=table, model=table.get_model()
    )

    services = service_type.on_event.call_args.args[0]
    assert {service.id for service in services} == {
        same_workspace.id,
        without_integration.id,
    }
