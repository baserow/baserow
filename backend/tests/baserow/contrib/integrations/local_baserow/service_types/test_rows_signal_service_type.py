from unittest.mock import Mock

import pytest

from baserow.contrib.database.table.models import Table
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
    LocalBaserowRowsDeletedTriggerServiceType,
    LocalBaserowRowsUpdatedTriggerServiceType,
)
from baserow.core.models import Agent as Identity
from baserow.core.services.registries import service_type_registry

ROWS_TRIGGER_TYPES = [
    LocalBaserowRowsCreatedTriggerServiceType,
    LocalBaserowRowsUpdatedTriggerServiceType,
    LocalBaserowRowsDeletedTriggerServiceType,
]


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


def identity_with_table(data_fixture) -> tuple[Identity, Table]:
    """A run identity with the default member role and an Orders table it reads."""

    workspace = data_fixture.create_workspace(user=data_fixture.create_user())
    database = data_fixture.create_database_application(
        workspace=workspace, name="Sales"
    )
    table = data_fixture.create_database_table(database=database, name="Orders")
    return Identity.objects.create(workspace=workspace, name="Reader"), table


@pytest.mark.parametrize("service_type_class", ROWS_TRIGGER_TYPES)
def test_rows_events_cannot_be_skipped(service_type_class):
    assert service_type_class().events_can_be_skipped is False


def test_rows_events_split_into_parts_without_changing_the_event():
    service_type = LocalBaserowRowsCreatedTriggerServiceType()
    payload = {"results": [{"id": i} for i in range(45)], "has_next_page": False}

    parts = service_type.split_event_payload(Mock(), payload, 20)

    assert [len(part["results"]) for part in parts] == [20, 20, 5]
    assert [part["results"][0]["id"] for part in parts] == [0, 20, 40]
    assert {part["has_next_page"] for part in parts} == {False}
    assert len(payload["results"]) == 45
    assert service_type.split_event_payload(Mock(), {"results": []}, 20) == [
        {"results": []}
    ]


@pytest.mark.parametrize("size", [0, -3])
def test_rows_events_split_into_parts_of_at_least_one_row(size):
    service_type = LocalBaserowRowsCreatedTriggerServiceType()
    payload = {"results": [{"id": 1}, {"id": 2}], "has_next_page": False}

    parts = service_type.split_event_payload(Mock(), payload, size)

    assert [part["results"] for part in parts] == [[{"id": 1}], [{"id": 2}]]


@pytest.mark.django_db
def test_rows_events_are_described_by_their_count_and_table(data_fixture):
    table = data_fixture.create_database_table(name="Orders")
    service = data_fixture.create_local_baserow_rows_created_service(
        table=table, integration=None
    )

    context = service.get_type().get_event_context(
        service, {"results": [{"id": 1}, {"id": 2}], "has_next_page": False}
    )

    assert context == {"count": 2, "table": "Orders"}


@pytest.mark.django_db
def test_rows_events_are_read_from_a_live_table_of_the_workspace(data_fixture):
    identity, table = identity_with_table(data_fixture)
    workspace = table.database.workspace
    elsewhere = data_fixture.create_database_table(name="Elsewhere")
    service_type = service_type_registry.get(
        LocalBaserowRowsCreatedTriggerServiceType.type
    )

    def can_read(on_table: Table | None, subject: Identity | None = identity) -> bool:
        service = data_fixture.create_local_baserow_rows_created_service(
            table=on_table, integration=None
        )
        return service_type.can_subject_read(service, subject, workspace)

    assert can_read(None, subject=None) is True
    assert can_read(table) is True
    assert can_read(table, subject=None) is False
    assert can_read(elsewhere) is False
    table.trashed = True
    table.save(update_fields=["trashed"])
    assert can_read(table) is False


@pytest.mark.django_db
def test_rows_triggers_offer_the_tables_whose_rows_the_subject_lists(data_fixture):
    identity, table = identity_with_table(data_fixture)
    workspace = table.database.workspace
    service_type = service_type_registry.get(
        LocalBaserowRowsCreatedTriggerServiceType.type
    )

    [database] = service_type.get_form_choices(identity, workspace)["databases"]

    assert (database["name"], database["views"]) == ("Sales", [])
    assert database["tables"] == [
        {
            "id": table.id,
            "database_id": table.database_id,
            "name": "Orders",
            "is_data_sync": False,
            "is_two_way_data_sync": False,
        }
    ]
    assert service_type.get_form_choices(None, workspace) == {"databases": []}
