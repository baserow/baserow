from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import PasswordField
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.models import RowHistory
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewDefaultValue
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import ExportApplicationsActionType
from baserow.core.handler import CoreHandler
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.snapshots.handler import SnapshotHandler
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.handler import user_template_copy_config
from baserow.core.utils import Progress


@pytest.mark.django_db
def test_field_creation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    assert len(PasswordField.objects.all()) == 1

    model = table.get_model()
    password = make_password("test")

    row = model.objects.create(**{f"field_{field.id}": password})

    # We don't expect the value to automatically be hashed, this will only be the
    # case if the row handler is used.
    assert getattr(row, f"field_{field.id}") == password


@pytest.mark.django_db
def test_row_creation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row_1 = row_handler.create_row(user=user, table=table, values={})
    row_2 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": None}}
    )
    row_3 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": make_password("test")}}
    )

    assert getattr(row_1, f"field_{field.id}") is None
    assert getattr(row_2, f"field_{field.id}") is None
    assert check_password("test", getattr(row_3, f"field_{field.id}"))


@pytest.mark.django_db
def test_row_update_already_empty(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": None}}
    )

    row_handler = RowHandler()
    row = row_handler.update_row(user=user, table=table, row=row, values={})

    assert getattr(row, f"field_{field.id}") is None

    row = row_handler.update_row(
        user=user, table=table, row=row, values={**{f"field_{field.id}": None}}
    )

    assert getattr(row, f"field_{field.id}") is None

    row = row_handler.update_row(
        user=user,
        table=table,
        row=row,
        values={**{f"field_{field.id}": make_password("test")}},
    )

    assert check_password("test", getattr(row, f"field_{field.id}"))


@pytest.mark.django_db
def test_row_update_with_value(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": make_password("test")}}
    )

    row_handler = RowHandler()
    row = row_handler.update_row(user=user, table=table, row=row, values={})

    assert check_password("test", getattr(row, f"field_{field.id}"))

    row = row_handler.update_row(
        user=user,
        table=table,
        row=row,
        values={**{f"field_{field.id}": make_password("test2")}},
    )

    assert check_password("test2", getattr(row, f"field_{field.id}"))

    row = row_handler.update_row(
        user=user, table=table, row=row, values={**{f"field_{field.id}": None}}
    )

    assert getattr(row, f"field_{field.id}") is None


@pytest.mark.django_db
def test_get_row_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row_1 = row_handler.create_row(user=user, table=table, values={})
    row_2 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": None}}
    )
    row_3 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": make_password("test")}}
    )

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.data["results"] == [
        {"id": row_1.id, "order": "1.00000000000000000000", f"field_{field.id}": None},
        {"id": row_2.id, "order": "2.00000000000000000000", f"field_{field.id}": None},
        # The password itself should never be exposed, it will be `True` if set.
        {"id": row_3.id, "order": "3.00000000000000000000", f"field_{field.id}": True},
    ]


@pytest.mark.django_db
def test_create_row_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    response = api_client.post(
        reverse(
            "api:database:rows:batch",
            kwargs={"table_id": table.id},
        ),
        {
            "items": [
                {},
                {
                    f"field_{field.id}": None,
                },
                {
                    f"field_{field.id}": "test",
                },
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    rows = table.get_model().objects.all()

    assert response.data == {
        "items": [
            {
                "id": rows[0].id,
                "order": "1.00000000000000000000",
                f"field_{field.id}": None,
            },
            {
                "id": rows[1].id,
                "order": "2.00000000000000000000",
                f"field_{field.id}": None,
            },
            # The password itself should never be exposed, it will be `True` if set.
            {
                "id": rows[2].id,
                "order": "3.00000000000000000000",
                f"field_{field.id}": True,
            },
        ]
    }

    with pytest.raises(TypeError):
        assert not check_password("test", getattr(rows[0], f"field_{field.id}"))

    with pytest.raises(TypeError):
        assert not check_password("test", getattr(rows[1], f"field_{field.id}"))

    assert check_password("test", getattr(rows[2], f"field_{field.id}"))


@pytest.mark.django_db
def test_row_update_with_empty_value_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": None}}
    )

    url = reverse(
        "api:database:rows:item",
        kwargs={"table_id": table.id, "row_id": row.id},
    )
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "id": row.id,
        "order": "1.00000000000000000000",
        f"field_{field.id}": None,
    }

    with pytest.raises(TypeError):
        row.refresh_from_db()
        assert not check_password("test", getattr(row, f"field_{field.id}"))

    response = api_client.patch(
        url,
        {f"field_{field.id}": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "id": row.id,
        "order": "1.00000000000000000000",
        f"field_{field.id}": None,
    }

    with pytest.raises(TypeError):
        row.refresh_from_db()
        assert not check_password("test", getattr(row, f"field_{field.id}"))

    response = api_client.patch(
        url,
        {f"field_{field.id}": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "id": row.id,
        "order": "1.00000000000000000000",
        f"field_{field.id}": True,
    }

    row.refresh_from_db()
    assert check_password("test", getattr(row, f"field_{field.id}"))


@pytest.mark.django_db
def test_row_update_with_value_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": make_password("test")}}
    )

    url = reverse(
        "api:database:rows:item",
        kwargs={"table_id": table.id, "row_id": row.id},
    )
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "id": row.id,
        "order": "1.00000000000000000000",
        f"field_{field.id}": True,
    }

    check_password("test", getattr(row, f"field_{field.id}"))

    response = api_client.patch(
        url,
        {f"field_{field.id}": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "id": row.id,
        "order": "1.00000000000000000000",
        f"field_{field.id}": None,
    }

    with pytest.raises(TypeError):
        row.refresh_from_db()
        assert not check_password("test", getattr(row, f"field_{field.id}"))

    response = api_client.patch(
        url,
        {f"field_{field.id}": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "id": row.id,
        "order": "1.00000000000000000000",
        f"field_{field.id}": True,
    }

    row.refresh_from_db()
    assert check_password("test", getattr(row, f"field_{field.id}"))


@pytest.mark.django_db
def test_check_history_content_for_password_field(data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": None}}
    )

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {"id": row.id, f"field_{field.id}": make_password("test2")},
            ],
        )

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {"id": row.id, f"field_{field.id}": make_password("test3")},
            ],
        )

    with freeze_time("2021-01-01 12:00"):
        action_type_registry.get_by_type(UpdateRowsActionType).do(
            user,
            table,
            [
                {"id": row.id, f"field_{field.id}": None},
            ],
        )

    history_entries = list(
        RowHistory.objects.order_by("row_id").values(
            "actor_id",
            "actor_type",
            "actor_name",
            "table_id",
            "row_id",
            "action_timestamp",
            "action_type",
            "before_values",
            "after_values",
            "fields_metadata",
        )
    )

    assert history_entries[0]["before_values"] == {field.db_column: False}
    assert history_entries[0]["after_values"] == {field.db_column: True}

    assert history_entries[1]["before_values"] == {field.db_column: True}
    assert history_entries[1]["after_values"] == {field.db_column: True}

    assert history_entries[2]["before_values"] == {field.db_column: True}
    assert history_entries[2]["after_values"] == {field.db_column: False}


@pytest.mark.django_db
def test_row_update_with_value_with_true_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="password",
        name="password1",
    )

    row_handler = RowHandler()
    row_1 = row_handler.create_row(user=user, table=table, values={})
    row_2 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": None}}
    )
    row_3 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{field.id}": make_password("test")}}
    )

    response = api_client.patch(
        reverse(
            "api:database:rows:batch",
            kwargs={"table_id": table.id},
        ),
        {
            "items": [
                {"id": row_1.id, f"field_{field.id}": True},
                {"id": row_2.id, f"field_{field.id}": True},
                {"id": row_3.id, f"field_{field.id}": True},
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.data == {
        "items": [
            {
                "id": row_1.id,
                "order": "1.00000000000000000000",
                f"field_{field.id}": None,
            },
            {
                "id": row_2.id,
                "order": "2.00000000000000000000",
                f"field_{field.id}": None,
            },
            {
                "id": row_3.id,
                "order": "3.00000000000000000000",
                f"field_{field.id}": True,
            },
        ]
    }

    with pytest.raises(TypeError):
        row_1.refresh_from_db()
        assert not check_password("test", getattr(row_1, f"field_{field.id}"))

    with pytest.raises(TypeError):
        row_2.refresh_from_db()
        assert not check_password("test", getattr(row_2, f"field_{field.id}"))

    assert check_password("test", getattr(row_3, f"field_{field.id}"))


@pytest.mark.undo_redo
@pytest.mark.django_db
def test_undo_update_to_text_field(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    password_field = data_fixture.create_password_field(table=table)

    row_handler = RowHandler()
    row_1 = row_handler.create_row(user=user, table=table, values={})
    row_2 = row_handler.create_row(
        user=user, table=table, values={**{f"field_{password_field.id}": None}}
    )

    row_3 = row_handler.create_row(
        user=user,
        table=table,
        values={**{f"field_{password_field.id}": make_password("test")}},
    )

    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, password_field, new_type_name="text"
    )

    model = table.get_model()
    rows = model.objects.all()

    assert getattr(rows[0], f"field_{password_field.id}") is None
    assert getattr(rows[1], f"field_{password_field.id}") is None
    assert getattr(rows[2], f"field_{password_field.id}") is None

    row_4 = row_handler.create_row(
        user=user,
        table=table,
        values={**{f"field_{password_field.id}": make_password("test")}},
    )

    ActionHandler.undo(user, [UpdateFieldActionType.scope(table.id)], session_id)

    model = table.get_model()
    rows = model.objects.all()

    assert getattr(rows[0], f"field_{password_field.id}") is None
    assert getattr(rows[1], f"field_{password_field.id}") is None
    assert check_password("test", getattr(rows[2], f"field_{password_field.id}"))
    assert getattr(rows[3], f"field_{password_field.id}") is None


@pytest.mark.field_autonumber
@pytest.mark.django_db
def test_duplicate_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    password_field = data_fixture.create_password_field(table=table)

    row_handler = RowHandler()
    row_handler.create_row(user=user, table=table, values={})
    row_handler.create_row(
        user=user, table=table, values={**{f"field_{password_field.id}": None}}
    )
    test_password = make_password("test")
    row_handler.create_row(
        user=user, table=table, values={**{f"field_{password_field.id}": test_password}}
    )

    duplicated_field, _ = FieldHandler().duplicate_field(
        user=user, field=password_field, duplicate_data=True
    )

    model = table.get_model()
    rows = model.objects.all()

    with pytest.raises(TypeError):
        rows[0].refresh_from_db()
        assert not check_password(
            "test", getattr(rows[0], f"field_{duplicated_field.id}")
        )

    with pytest.raises(TypeError):
        rows[1].refresh_from_db()
        assert not check_password(
            "test", getattr(rows[1], f"field_{duplicated_field.id}")
        )

    assert check_password("test", getattr(rows[2], f"field_{duplicated_field.id}"))


@pytest.mark.django_db
def test_user_template_export_empties_password_cells(data_fixture):
    table = data_fixture.create_database_table()
    text_field = data_fixture.create_text_field(table=table, name="Name")
    password_field = data_fixture.create_password_field(
        table=table, name="Password", allow_endpoint_authentication=True
    )
    password = make_password("test")
    model = table.get_model()
    model.objects.create(
        **{text_field.db_column: "Set", password_field.db_column: password}
    )
    model.objects.create(**{text_field.db_column: "Unset"})

    def export(config):
        [serialized_table] = DatabaseApplicationType().export_tables_serialized(
            [table], config
        )
        rows = sorted(serialized_table["rows"], key=lambda row: row["id"])
        return serialized_table, rows

    serialized_table, rows = export(user_template_copy_config())

    assert [row[text_field.db_column] for row in rows] == ["Set", "Unset"]
    assert [row[password_field.db_column] for row in rows] == [None, None]
    [serialized_field] = [
        field
        for field in serialized_table["fields"]
        if field["id"] == password_field.id
    ]
    assert serialized_field["type"] == "password"
    assert serialized_field["allow_endpoint_authentication"] is True

    # A workspace export keeps the hash.
    _, rows = export(
        ImportExportConfig(include_permission_data=False, reduce_disk_space_usage=False)
    )
    assert [row[password_field.db_column] for row in rows] == [password, None]


def _copy_by_workspace_export_import(data_fixture, user, table):
    data_fixture.create_import_export_trusted_source()
    handler = ImportExportHandler()
    resource = ExportApplicationsActionType.do(
        user, table.database.workspace, [table.database]
    )
    target = data_fixture.create_workspace(user=user)
    export_path = handler.get_export_storage_path(resource.get_archive_name())
    with get_default_storage().open(export_path, "rb") as archive:
        import_resource = handler.create_resource_from_file(user, "export.zip", archive)
    [database] = handler.import_workspace_applications(user, target, import_resource)
    return Table.objects.get(database=database)


def _copy_by_application_duplicate(data_fixture, user, table):
    database = CoreHandler().duplicate_application(user, table.database)
    return Table.objects.get(database=database)


def _copy_by_table_duplicate(data_fixture, user, table):
    return TableHandler().duplicate_table(user, table)


def _copy_by_snapshot_create_restore(data_fixture, user, table):
    snapshot = data_fixture.create_snapshot(
        snapshot_from_application=table.database, name="Snapshot", created_by=user
    )
    SnapshotHandler().perform_create(snapshot, Progress(total=100))
    snapshot.refresh_from_db()
    database = SnapshotHandler().perform_restore(snapshot, Progress(total=100))
    return Table.objects.get(database=database)


@pytest.mark.usefixtures("use_tmp_media_root")
@pytest.mark.parametrize(
    "copy",
    [
        pytest.param(
            _copy_by_workspace_export_import,
            id="workspace_export_import",
            marks=[
                pytest.mark.import_export_workspace,
                pytest.mark.django_db(transaction=True),
            ],
        ),
        pytest.param(
            _copy_by_application_duplicate,
            id="application_duplicate",
            marks=pytest.mark.django_db,
        ),
        pytest.param(
            _copy_by_table_duplicate, id="table_duplicate", marks=pytest.mark.django_db
        ),
        pytest.param(
            _copy_by_snapshot_create_restore,
            id="snapshot_create_restore",
            marks=pytest.mark.django_db,
        ),
    ],
)
def test_password_values_are_kept_outside_user_templates(data_fixture, copy):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    password_field = data_fixture.create_password_field(table=table, name="Password")
    view = data_fixture.create_grid_view(table=table)
    password = make_password("test")
    table.get_model().objects.create(**{password_field.db_column: password})
    with transaction.atomic():
        ViewHandler().update_view_default_values(
            user,
            view,
            [{"field": password_field.id, "enabled": True, "value": "default"}],
        )

    copied_table = copy(data_fixture, user, table)

    copied_field = copied_table.field_set.get(name="Password")
    assert copied_field.id != password_field.id
    [copied_value] = copied_table.get_model().objects.values_list(
        copied_field.db_column, flat=True
    )
    assert copied_value == password
    assert check_password("test", copied_value)
    copied_default = ViewDefaultValue.objects.get(
        view__table=copied_table, field=copied_field
    )
    assert copied_default.enabled is True
