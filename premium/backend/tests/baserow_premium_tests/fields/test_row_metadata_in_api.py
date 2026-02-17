from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.table.handler import TableHandler
from baserow_premium.fields.ai_field_metadata import AIFieldMetadataHandler


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_batch_create_rows_includes_ai_field_metadata(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    text_field = premium_data_fixture.create_text_field(table=table)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "hello"})

    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    url = f"{url}?include_metadata=true"
    response = api_client.post(
        url,
        {"items": [{f"field_{text_field.id}": "new"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    data = response.json()

    # The newly created row won't have AI metadata, but the metadata.rows key
    # should be present when include_metadata=true.
    assert "metadata" in data
    assert "rows" in data["metadata"]


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_batch_update_rows_includes_ai_field_metadata(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    text_field = premium_data_fixture.create_text_field(table=table)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "hello"})

    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    url = f"{url}?include_metadata=true"
    response = api_client.patch(
        url,
        {"items": [{"id": row.id, f"field_{text_field.id}": "updated"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    data = response.json()

    assert "metadata" in data
    rows_metadata = data["metadata"]["rows"]
    row_meta = rows_metadata.get(str(row.id), {})
    assert row_meta.get("ai_field", {}).get(str(ai_field.id)) == {
        "status": "generating"
    }


@pytest.mark.django_db
@pytest.mark.field_ai
@override_settings(DEBUG=True)
def test_batch_update_rows_without_metadata_flag_excludes_rows(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    database = premium_data_fixture.create_database_application(user=user)
    table = premium_data_fixture.create_database_table(database=database)
    text_field = premium_data_fixture.create_text_field(table=table)
    ai_field = premium_data_fixture.create_ai_field(table=table, name="AI")

    model = table.get_model()
    row = model.objects.create(**{f"field_{text_field.id}": "hello"})

    TableHandler().ensure_field_metadata_column_exists(table)
    AIFieldMetadataHandler.set_generating(ai_field, row.id)

    url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
    response = api_client.patch(
        url,
        {"items": [{"id": row.id, f"field_{text_field.id}": "updated"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert "metadata" not in data
