from django.contrib.auth.hashers import check_password, make_password
from django.urls import reverse

import pytest
from freezegun import freeze_time

from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import PasswordField
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.rows.models import RowHistory
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry


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
