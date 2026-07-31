from unittest.mock import patch

from django.db import connection
from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
)

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_create_button_field_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name")

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Open profile",
            "type": "button",
            "label": "Open",
            "url_formula": {
                "formula": (
                    f"concat('https://example.com/', get('fields.field_{text_field.id}'))"
                ),
                "mode": "simple",
            },
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    data = response.json()
    assert data["type"] == "button"
    assert data["label"] == "Open"
    assert data["read_only"] is True
    assert data["error"] is None
    assert f"field_{text_field.id}" in data["url_formula"]["formula"]


@pytest.mark.django_db
def test_create_button_field_with_flag_disabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    with override_settings(FEATURE_FLAGS=[]):
        response = api_client.post(
            reverse("api:database:fields:list", kwargs={"table_id": table.id}),
            {"name": "Open profile", "type": "button", "label": "Open"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"


@pytest.mark.django_db
def test_existing_button_field_keeps_working_with_flag_disabled(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table)
    button_field = data_fixture.create_button_field(table=table, name="btn")

    # The type stays registered when the flag is off, so tables containing an
    # existing button field must keep listing fields and rows normally.
    with override_settings(FEATURE_FLAGS=[]):
        response = api_client.get(
            reverse("api:database:fields:list", kwargs={"table_id": table.id}),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert any(
            field["id"] == button_field.id and field["type"] == "button"
            for field in response.json()
        )

        response = api_client.get(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_create_button_field_with_invalid_formula_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Broken",
            "type": "button",
            "url_formula": {"formula": "concat(broken", "mode": "simple"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_button_field_cell_is_read_only(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    model = table.get_model()
    row = model.objects.create()

    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        {f"field_{button_field.id}": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_button_field_row_value_is_null(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    model = table.get_model()
    row = model.objects.create()

    response = api_client.get(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[f"field_{button_field.id}"] is None


@pytest.mark.django_db
def test_button_field_error_when_referenced_field_trashed(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    button_field = data_fixture.create_button_field(
        table=table,
        url_formula={
            "formula": f"get('fields.field_{text_field.id}')",
            "mode": "simple",
        },
    )

    assert button_field.error is None
    FieldHandler().delete_field(user, text_field)
    button_field.refresh_from_db()
    assert button_field.error == (
        "The formula references a field that no longer exists."
    )


@pytest.mark.django_db
@patch("baserow.contrib.database.fields.signals.field_restored.send")
def test_restoring_referenced_field_clears_button_field_error(
    field_restored_mock, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    button_field = FieldHandler().create_field(
        user,
        table,
        "button",
        name="btn",
        label="Open",
        url_formula={
            "formula": f"get('fields.field_{text_field.id}')",
            "mode": "simple",
        },
    )

    FieldHandler().delete_field(user, text_field)
    button_field.refresh_from_db()
    assert button_field.error is not None

    # Restoring the referenced field must report the button field as updated so
    # the client re-fetches it and sees the error is gone. This is what
    # `field_dependency_updated` is for.
    TrashHandler.restore_item(user, "field", text_field.id)
    related = field_restored_mock.call_args[1]["related_fields"]
    assert button_field.id in [f.id for f in related]

    button_field.refresh_from_db()
    assert button_field.error is None


@pytest.mark.django_db
def test_duplicate_table_remaps_button_url_formula_references(data_fixture):
    from baserow.contrib.database.table.handler import TableHandler

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    data_fixture.create_button_field(
        table=table,
        name="btn",
        url_formula={
            "formula": f"get('fields.field_{text_field.id}')",
            "mode": "simple",
        },
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    new_button = ButtonField.objects.get(table=duplicated_table)
    new_text_field_id = duplicated_table.field_set.exclude(id=new_button.id).get().id

    assert new_button.url_formula["formula"] == (
        f"get('fields.field_{new_text_field_id}')"
    )
    assert new_button.url_formula["mode"] == "simple"
    assert new_button.error is None


@pytest.mark.django_db
def test_duplicate_table_keeps_button_url_formula_mode(data_fixture):
    from baserow.contrib.database.table.handler import TableHandler

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    data_fixture.create_button_field(
        table=table,
        name="btn",
        url_formula={
            "formula": f"get('fields.field_{text_field.id}')",
            "mode": "advanced",
        },
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    new_button = ButtonField.objects.get(table=duplicated_table)
    new_text_field_id = duplicated_table.field_set.exclude(id=new_button.id).get().id

    # Remapping must not reset the mode, otherwise the copy opens in the wrong
    # editor and, for raw formulas, stops resolving entirely.
    assert new_button.url_formula["mode"] == "advanced"
    assert new_button.url_formula["formula"] == (
        f"get('fields.field_{new_text_field_id}')"
    )


@pytest.mark.django_db
def test_duplicate_table_keeps_raw_button_url_formula_working(data_fixture):
    from baserow.contrib.database.table.handler import TableHandler

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_button_field(
        table=table,
        name="btn",
        url_formula={"formula": "https://example.com?x=(1", "mode": "raw"},
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    new_button = ButtonField.objects.get(table=duplicated_table)

    # A raw formula is literal text that is never parsed. Downgrading it to
    # `simple` would make this unparseable and break the duplicated button.
    assert new_button.url_formula["mode"] == "raw"
    assert new_button.url_formula["formula"] == "https://example.com?x=(1"
    assert new_button.error is None


@pytest.mark.django_db
def test_duplicate_table_with_button_field_broken_references(data_fixture):
    from baserow.contrib.database.table.handler import TableHandler

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_button_field(
        table=table,
        name="btn",
        url_formula={
            "formula": "concat('test:',get('fields.field_0'))",
            "mode": "simple",
        },
    )

    # A reference to a field missing from the id mapping must not fail the
    # duplication; the formula is kept as-is.
    duplicated_table = TableHandler().duplicate_table(user, table)
    new_button = ButtonField.objects.get(table=duplicated_table)

    assert new_button.url_formula["formula"] == (
        "concat('test:',get('fields.field_0'))"
    )


@pytest.mark.django_db
def test_button_field_has_no_database_column(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = FieldHandler().create_field(
        user, table, "button", name="btn", label="Open"
    )

    model = table.get_model()
    model_field = model._meta.get_field(button_field.db_column)
    # The field exists on the model so the handler can look it up, but it is
    # not concrete, so no column is created and rows never select it.
    assert model_field.column is None
    assert model_field.concrete is False
    assert model_field not in model._meta.concrete_fields

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            [table.get_database_table_name()],
        )
        assert button_field.db_column not in [row[0] for row in cursor.fetchall()]

    row = model.objects.create()
    assert getattr(row, button_field.db_column) is None
    assert getattr(model.objects.get(pk=row.id), button_field.db_column) is None


@pytest.mark.django_db
def test_converting_to_and_from_a_button_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="convert me")
    model = table.get_model()
    row = model.objects.create(**{field.db_column: "keep"})

    # Converting into a button drops the column, converting back recreates it.
    FieldHandler().update_field(user, field, new_type_name="button", label="Open")
    button_model = table.get_model()
    assert button_model._meta.get_field(field.db_column).column is None
    assert getattr(button_model.objects.get(pk=row.id), field.db_column) is None

    FieldHandler().update_field(user, field.specific, new_type_name="text")
    text_model = table.get_model()
    assert text_model._meta.get_field(field.db_column).column == field.db_column
    # The button held no data, so the recreated column starts empty.
    assert getattr(text_model.objects.get(pk=row.id), field.db_column) is None


@pytest.mark.django_db
def test_updating_an_existing_button_field_with_flag_disabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, name="btn")

    # Only creation is gated: an existing button field stays editable so that
    # turning the flag off never traps a table.
    with override_settings(FEATURE_FLAGS=[]):
        response = api_client.patch(
            reverse("api:database:fields:item", kwargs={"field_id": button_field.id}),
            {"label": "Renamed"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    assert response.json()["label"] == "Renamed"


@pytest.mark.django_db
def test_converting_a_field_to_button_with_flag_disabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    # Converting another type into a button is a creation, so it is gated.
    with override_settings(FEATURE_FLAGS=[]):
        response = api_client.patch(
            reverse("api:database:fields:item", kwargs={"field_id": text_field.id}),
            {"type": "button", "label": "Open"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"


@pytest.mark.django_db
def test_deleting_a_button_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = FieldHandler().create_field(
        user, table, "button", name="btn", label="Open"
    )

    # There is no column to drop, so the schema editor has to skip it rather
    # than fail on a field it can't find.
    FieldHandler().delete_field(user, button_field)
    TrashHandler.permanently_delete(button_field)

    assert not ButtonField.objects.filter(id=button_field.id).exists()
    assert table.get_model().objects.count() == 0


@pytest.mark.django_db
def test_create_button_field_without_a_label_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # The label is the only text the button shows, so it can't be left out.
    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Open profile",
            "type": "button",
            "url_formula": {"formula": "'https://example.com'", "mode": "simple"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_BUTTON_FIELD_LABEL_NOT_PROVIDED"


@pytest.mark.django_db
@pytest.mark.parametrize("label", ["", "   "])
def test_create_button_field_with_a_blank_label_via_api(
    api_client, data_fixture, label
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {"name": "Open profile", "type": "button", "label": label},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_BUTTON_FIELD_LABEL_NOT_PROVIDED"


@pytest.mark.django_db
def test_emptying_a_button_field_label_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Open")

    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": button_field.id}),
        {"label": ""},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_BUTTON_FIELD_LABEL_NOT_PROVIDED"
    button_field.refresh_from_db()
    assert button_field.label == "Open"


@pytest.mark.django_db
def test_updating_a_button_field_without_a_label_keeps_the_existing_one(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Open")

    # An update that doesn't mention the label isn't a request to empty it.
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": button_field.id}),
        {"url_formula": {"formula": "'https://example.com'", "mode": "simple"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["label"] == "Open"


@pytest.mark.django_db
def test_converting_a_field_to_button_without_a_label_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)

    # Converting into a button creates one, so the label is required here too.
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": text_field.id}),
        {"type": "button"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_BUTTON_FIELD_LABEL_NOT_PROVIDED"


@pytest.mark.django_db
def test_button_field_is_not_returned_by_the_public_view_info_endpoint(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = data_fixture.create_button_field(
        table=table, name="btn", label="Open"
    )
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    # Visible field options aren't enough: the label and the URL formula are
    # configuration and must never reach an anonymous visitor.
    data_fixture.create_grid_view_field_option(grid_view, text_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, button_field, hidden=False)

    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": grid_view.slug})
    )

    assert response.status_code == HTTP_200_OK, response.json()
    returned_ids = [field["id"] for field in response.json()["fields"]]
    assert returned_ids == [text_field.id]


@pytest.mark.django_db
def test_button_field_is_not_returned_in_public_view_rows(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name")
    button_field = data_fixture.create_button_field(
        table=table, name="btn", label="Open"
    )
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, text_field, hidden=False)
    data_fixture.create_grid_view_field_option(grid_view, button_field, hidden=False)
    table.get_model().objects.create(**{text_field.db_column: "ada"})

    response = api_client.get(
        reverse("api:database:views:grid:public_rows", kwargs={"slug": grid_view.slug})
        + "?include=field_options"
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert button_field.db_column not in response_json["results"][0]
    assert text_field.db_column in response_json["results"][0]
    assert str(button_field.id) not in response_json["field_options"]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_button_field_changes_are_not_broadcast_to_public_views(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = FieldHandler().create_field(
        user, table, "button", name="btn", label="Open"
    )
    grid_view = data_fixture.create_grid_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(grid_view, button_field, hidden=False)

    FieldHandler().update_field(user, button_field, label="Renamed")

    # The realtime payload carries the label and the URL formula too, so the
    # public view page must not receive it either.
    assert [
        call
        for call in mock_broadcast_to_channel_group.delay.mock_calls
        if call.args and call.args[0] == f"view-{grid_view.slug}"
    ] == []


@pytest.mark.django_db
def test_button_field_reports_whether_it_has_actions(api_client, data_fixture):
    from baserow.contrib.database.workflow_actions.models import (
        CreateRowWorkflowAction,
    )

    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")

    def get_payload():
        response = api_client.get(
            reverse("api:database:fields:item", kwargs={"field_id": button_field.id}),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK, response.json()
        return response.json()

    assert get_payload()["has_workflow_actions"] is False

    data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )

    assert get_payload()["has_workflow_actions"] is True
