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
