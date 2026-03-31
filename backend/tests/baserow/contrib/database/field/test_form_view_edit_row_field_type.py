from urllib.parse import parse_qs, urlparse

from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormViewEditRowField
from baserow.contrib.database.fields.utils.row_edit import (
    generate_row_edit_token,
    verify_and_decode_edit_token,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.exceptions import ViewNotInTable
from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db
def test_generate_row_edit_token_is_deterministic():
    """The same inputs must always produce the same token."""
    token1 = generate_row_edit_token(view_slug="slug1", field_id=2, cell_uuid="abc-123")
    token2 = generate_row_edit_token(view_slug="slug1", field_id=2, cell_uuid="abc-123")
    assert token1 == token2


@pytest.mark.django_db
def test_generate_row_edit_token_differs_by_input():
    """Different inputs must produce different tokens."""
    t1 = generate_row_edit_token(view_slug="slug1", field_id=2, cell_uuid="uuid-a")
    t2 = generate_row_edit_token(view_slug="slug2", field_id=2, cell_uuid="uuid-a")
    t3 = generate_row_edit_token(view_slug="slug1", field_id=99, cell_uuid="uuid-a")
    t4 = generate_row_edit_token(view_slug="slug1", field_id=2, cell_uuid="uuid-b")
    assert len({t1, t2, t3, t4}) == 4


@pytest.mark.django_db
def test_verify_and_decode_edit_token_valid():
    """A freshly generated token must decode back to the original values."""
    token = generate_row_edit_token(
        view_slug="test-slug", field_id=15, cell_uuid="my-uuid"
    )
    data = verify_and_decode_edit_token(token)
    assert data == {"view_slug": "test-slug", "field_id": 15, "cell_uuid": "my-uuid"}


@pytest.mark.django_db
def test_verify_and_decode_edit_token_tampered():
    """A tampered token must return None."""
    token = generate_row_edit_token(view_slug="slug", field_id=3, cell_uuid="uuid")
    assert verify_and_decode_edit_token(token + "X") is None
    assert verify_and_decode_edit_token("totallyinvalid") is None
    assert verify_and_decode_edit_token("") is None


@pytest.mark.django_db
def test_create_form_view_edit_row_field(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)

    handler = FieldHandler()
    field = handler.create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    assert isinstance(field.specific, FormViewEditRowField)
    assert field.specific.form_view_id == form_view.id
    assert FormViewEditRowField.objects.filter(id=field.id).exists()


@pytest.mark.django_db
def test_create_form_view_edit_row_field_wrong_table(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    other_table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=other_table)

    handler = FieldHandler()
    with pytest.raises(ViewNotInTable):
        handler.create_field(
            user=user,
            table=table,
            type_name="form_view_edit_row",
            name="Edit link",
            form_view_id=form_view.id,
        )


@pytest.mark.django_db
def test_create_form_view_edit_row_field_wrong_table_via_api(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    other_table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=other_table)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Edit link",
            "type": "form_view_edit_row",
            "form_view_id": form_view.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_VIEW_NOT_IN_TABLE"


@pytest.mark.django_db
def test_field_excluded_from_form_view_active_options(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)

    handler = FieldHandler()
    handler.create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    active_field_ids = [opt.field_id for opt in form_view.active_field_options]
    edit_row_field_ids = list(
        FormViewEditRowField.objects.filter(table=table).values_list("id", flat=True)
    )
    for fid in edit_row_field_ids:
        assert fid not in active_field_ids


@pytest.mark.django_db
def test_create_field_on_table_with_existing_rows(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    # Create multiple rows before adding the edit-row field.
    for i in range(5):
        RowHandler().create_row(
            user=user,
            table=table,
            values={f"field_{text_field.id}": f"Row {i}"},
        )

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Edit link",
            "type": "form_view_edit_row",
            "form_view_id": form_view.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()

    field_id = response.json()["id"]
    model = table.get_model()
    uuids = list(
        model.objects.values_list(f"field_{field_id}", flat=True).order_by("id")
    )

    # All UUIDs must be non-empty and unique.
    assert all(u is not None for u in uuids), f"Bad UUIDs: {uuids}"
    assert len(set(uuids)) == 5, f"Duplicate UUIDs found: {uuids}"


@pytest.mark.django_db
def test_update_field_preserves_unique_uuids(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    for i in range(3):
        RowHandler().create_row(
            user=user,
            table=table,
            values={f"field_{text_field.id}": f"Row {i}"},
        )

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Edit link",
            "type": "form_view_edit_row",
            "form_view_id": form_view.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    field_id = response.json()["id"]

    # Update the field without changing the type (simulates a rename or
    # no-op update from the frontend).
    response = api_client.patch(
        reverse("api:database:fields:item", kwargs={"field_id": field_id}),
        {
            "name": "Edit link renamed",
            "type": "form_view_edit_row",
            "form_view_id": form_view.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    model = table.get_model()
    uuids = list(
        model.objects.values_list(f"field_{field_id}", flat=True).order_by("id")
    )

    assert all(u is not None for u in uuids), f"Bad UUIDs: {uuids}"
    assert len(set(uuids)) == 3, f"Duplicate UUIDs after update: {uuids}"


@pytest.mark.django_db
def test_row_serializer_includes_edit_url(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    handler = FieldHandler()
    edit_field = handler.create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={f"field_{text_field.id}": "Hello"},
    )

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    edit_url = results[0][f"field_{edit_field.id}"]
    assert edit_url is not None
    assert form_view.slug in edit_url
    assert "edit_token=" in edit_url

    # Verify the token embedded in the URL is valid
    parsed = urlparse(edit_url)
    qs = parse_qs(parsed.query)
    token_val = qs["edit_token"][0]
    decoded = verify_and_decode_edit_token(token_val)
    assert decoded is not None
    assert decoded["view_slug"] == form_view.slug
    assert decoded["field_id"] == edit_field.id

    # The cell_uuid in the token must match the value stored in the row.
    model = table.get_model()
    row_instance = model.objects.get(id=row.id)
    cell_uuid = str(getattr(row_instance, f"field_{edit_field.id}"))
    assert decoded["cell_uuid"] == cell_uuid


@pytest.mark.django_db
def test_create_field_via_api_includes_form_view_id(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    response = api_client.post(
        reverse("api:database:fields:list", kwargs={"table_id": table.id}),
        {
            "name": "Edit link",
            "type": "form_view_edit_row",
            "form_view_id": form_view.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    field_data = response.json()
    field_id = field_data["id"]
    assert field_data["type"] == "form_view_edit_row"
    db_field = FormViewEditRowField.objects.get(id=field_id)
    assert db_field.form_view_id == form_view.id, (
        f"form_view_id not saved in DB: got {db_field.form_view_id}"
    )
    assert field_data.get("form_view_id") == form_view.id, (
        f"Expected form_view_id={form_view.id} in response but got: {field_data}"
    )

    RowHandler().create_row(user=user, table=table, values={})

    # List rows and confirm the edit URL is present
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    edit_url = results[0][f"field_{field_id}"]
    assert edit_url is not None, (
        f"Expected a URL for field_{field_id} but got None. Full row: {results[0]}"
    )
    assert form_view.slug in edit_url
    assert "edit_token=" in edit_url


@pytest.mark.django_db
def test_grid_view_includes_edit_url(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)
    grid_view = data_fixture.create_grid_view(table=table)

    handler = FieldHandler()
    edit_field = handler.create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={f"field_{text_field.id}": "Hello"},
    )

    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    results = response.json()["results"]
    assert len(results) == 1
    edit_url = results[0][f"field_{edit_field.id}"]
    assert edit_url is not None, (
        f"Expected a URL for field_{edit_field.id} but got None. "
        f"Full row response: {results[0]}"
    )
    assert form_view.slug in edit_url
    assert "edit_token=" in edit_url

    parsed = urlparse(edit_url)
    qs = parse_qs(parsed.query)
    token_val = qs["edit_token"][0]
    decoded = verify_and_decode_edit_token(token_val)
    assert decoded is not None
    assert decoded["view_slug"] == form_view.slug
    assert decoded["field_id"] == edit_field.id

    # The cell_uuid in the token must match the stored value.
    model = table.get_model()
    row_instance = model.objects.get(id=row.id)
    cell_uuid = str(getattr(row_instance, f"field_{edit_field.id}"))
    assert decoded["cell_uuid"] == cell_uuid


@pytest.mark.django_db
def test_export_includes_edit_url(data_fixture):
    """CSV export must include the computed edit URL for each row."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    edit_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    RowHandler().create_row(user=user, table=table, values={})

    from baserow.contrib.database.fields.registries import field_type_registry

    field_type = field_type_registry.get("form_view_edit_row")
    model = table.get_model()
    field_object = next(
        fo for fo in model.get_field_objects() if fo["field"].id == edit_field.id
    )

    row_instance = model.objects.first()
    value = getattr(row_instance, field_object["name"])
    export_value = field_type.get_export_value(value, field_object)

    assert export_value, "Expected a non-empty export URL"
    assert form_view.slug in export_value
    assert "edit_token=" in export_value


@pytest.mark.django_db
def test_convert_form_view_edit_row_to_text(data_fixture):
    """Converting a form_view_edit_row field to a text field must not crash."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    handler = FieldHandler()
    edit_field = handler.create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    RowHandler().create_row(user=user, table=table, values={})

    handler.update_field(user=user, field=edit_field, new_type_name="text")

    from baserow.contrib.database.fields.models import TextField

    assert TextField.objects.filter(id=edit_field.id).exists()
    assert not FormViewEditRowField.objects.filter(id=edit_field.id).exists()


@pytest.mark.django_db
def test_convert_text_to_form_view_edit_row(data_fixture):
    """Converting a text field to a form_view_edit_row field must not crash."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    handler = FieldHandler()
    text_field = handler.create_field(
        user=user,
        table=table,
        type_name="text",
        name="My field",
    )

    RowHandler().create_row(
        user=user, table=table, values={f"field_{text_field.id}": "hello"}
    )

    handler.update_field(
        user=user,
        field=text_field,
        new_type_name="form_view_edit_row",
        form_view_id=form_view.id,
    )

    assert FormViewEditRowField.objects.filter(id=text_field.id).exists()

    # Verify the converted field has a UUID backfilled.
    model = table.get_model()
    row = model.objects.first()
    cell_uuid = str(getattr(row, f"field_{text_field.id}"))
    assert cell_uuid is not None and len(cell_uuid) == 36


@pytest.mark.django_db
def test_duplicate_table_remaps_form_view_id(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    edit_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    assert edit_field.form_view_id == form_view.id

    new_table = TableHandler().duplicate_table(user, table)

    new_edit_field = FormViewEditRowField.objects.get(table=new_table)
    # The duplicated field must NOT point to the original form view.
    assert new_edit_field.form_view_id != form_view.id
    # It must point to a form view that belongs to the new table.
    assert new_edit_field.form_view_id is not None
    assert new_edit_field.form_view.table_id == new_table.id


@pytest.mark.django_db
def test_rotating_slug_invalidates_edit_urls(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    form_view = data_fixture.create_form_view(table=table, public=True)

    edit_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="form_view_edit_row",
        name="Edit link",
        form_view_id=form_view.id,
    )

    RowHandler().create_row(user=user, table=table, values={})

    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    old_url = response.json()["results"][0][f"field_{edit_field.id}"]
    old_slug = form_view.slug
    assert old_slug in old_url

    ViewHandler().rotate_view_slug(user, form_view)
    form_view.refresh_from_db()
    new_slug = form_view.slug
    assert new_slug != old_slug

    # Fetch the edit URL again — it must contain the new slug.
    response = api_client.get(
        reverse("api:database:rows:list", kwargs={"table_id": table.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    new_url = response.json()["results"][0][f"field_{edit_field.id}"]
    assert new_slug in new_url
    assert old_slug not in new_url
