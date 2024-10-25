from django.test.utils import override_settings
from django.urls import reverse

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.models import License
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.core.db import specific_iterator
from baserow.test_utils.helpers import setup_interesting_test_table
from baserow_enterprise.data_sync.baserow_table_data_sync import (
    BaserowFieldDataSyncProperty,
)
from baserow_enterprise.data_sync.models import LocalBaserowTableDataSync


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    field_1 = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )
    field_2 = enterprise_data_fixture.create_number_field(
        table=source_table, name="Number", primary=False, number_decimal_places=2
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{field_1.id}", f"field_{field_2.id}"],
        source_table_id=source_table.id,
    )

    assert isinstance(data_sync, LocalBaserowTableDataSync)
    assert data_sync.source_table_id == source_table.id
    assert data_sync.authorized_user_id == user.id

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 3
    assert fields[0].name == "Row ID"
    assert isinstance(fields[0], NumberField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[1].name == "Text"
    assert fields[1].primary is False
    assert fields[1].read_only is True
    assert fields[1].immutable_type is True
    assert fields[1].immutable_properties is True
    assert fields[2].name == "Number"
    assert fields[2].primary is False
    assert fields[2].read_only is True
    assert fields[2].immutable_type is True
    assert fields[2].immutable_properties is True
    assert fields[2].number_decimal_places == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_table_table_does_not_exist(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError):
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="local_baserow_table",
            synced_properties=["id"],
            source_table_id=0,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_table_without_access_to_source_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(name="Source")
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError):
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="local_baserow_table",
            synced_properties=["id"],
            source_table_id=source_table.id,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table_source_table_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id"],
        source_table_id=source_table.id,
    )

    data_sync.source_table = None
    data_sync.save()

    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_sync is None
    assert data_sync.last_error == "The source table doesn't exist."


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table_no_access_authorized_user(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user_2 = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id"],
        source_table_id=source_table.id,
    )

    data_sync.authorized_user = user_2
    data_sync.save()

    data_sync = handler.sync_data_sync_table(user=user, data_sync=data_sync)
    assert data_sync.last_sync is None
    assert (
        data_sync.last_error == "The authorized user doesn't have access to the table."
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    field_1 = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )
    field_2 = enterprise_data_fixture.create_number_field(
        table=source_table, name="Number", primary=False, number_decimal_places=2
    )
    source_model = source_table.get_model()
    source_row_1 = source_model.objects.create(
        **{
            f"field_{field_1.id}": "Test",
            f"field_{field_2.id}": 2,
        }
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{field_1.id}", f"field_{field_2.id}"],
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    row_id_field = fields[0]
    field_1_field = fields[1]
    field_2_field = fields[2]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 1
    row = model.objects.all().first()
    assert getattr(row, f"field_{row_id_field.id}") == source_row_1.id
    assert getattr(row, f"field_{field_1_field.id}") == getattr(
        source_row_1, f"field_{field_1.id}"
    )
    assert getattr(row, f"field_{field_2_field.id}") == getattr(
        source_row_1, f"field" f"_{field_2.id}"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table_with_interesting_table_as_source(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    source_table, user, *_ = setup_interesting_test_table(enterprise_data_fixture)
    source_fields = [
        field
        for field in specific_iterator(source_table.field_set.all())
        if field_type_registry.get_by_model(field).type
        in BaserowFieldDataSyncProperty.supported_field_types
    ]

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    synced_properties = ["id"] + [f"field_{field.id}" for field in source_fields]

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=synced_properties,
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 2
    blank_row = rows[0]
    row = rows[1]

    results = {}
    blank_results = {}
    for field in model._field_objects.values():
        value = field["type"].get_human_readable_value(
            getattr(row, field["name"]), field
        )
        results[field["field"].name] = value
        blank_value = field["type"].get_human_readable_value(
            getattr(blank_row, field["name"]), field
        )
        blank_results[field["field"].name] = blank_value

    assert blank_results == {
        "Row ID": "1",
        "boolean": "False",
        "date_eu": "",
        "date_us": "",
        "datetime_eu": "",
        "datetime_eu_tzone_hidden": "",
        "datetime_eu_tzone_visible": "",
        "datetime_us": "",
        "duration_dh": "",
        "duration_dhm": "",
        "duration_dhms": "",
        "duration_hm": "",
        "duration_hms": "",
        "duration_hms_s": "",
        "duration_hms_ss": "",
        "duration_hms_sss": "",
        "email": "",
        "file": "",
        "long_text": "",
        "negative_decimal": "",
        "negative_int": "",
        "phone_number": "",
        "positive_decimal": "",
        "positive_int": "",
        "rating": "0",
        "text": "",
        "url": "",
        "created_on_date_eu": "02/01/2021",
        "created_on_date_us": "01/02/2021",
        "created_on_datetime_eu": "02/01/2021 12:00",
        "created_on_datetime_us": "01/02/2021 12:00",
        "created_on_datetime_eu_tzone": "02/01/2021 13:00",
        "last_modified_date_eu": "02/01/2021",
        "last_modified_date_us": "01/02/2021",
        "last_modified_datetime_eu": "02/01/2021 12:00",
        "last_modified_datetime_us": "01/02/2021 12:00",
        "last_modified_datetime_eu_tzone": "02/01/2021 13:00",
        "autonumber": "1",
        "ai": "",
        "uuid": "00000000-0000-4000-8000-000000000001",
    }
    assert results == {
        "Row ID": "2",
        "boolean": "True",
        "date_eu": "01/02/2020",
        "date_us": "02/01/2020",
        "datetime_eu": "01/02/2020 01:23",
        "datetime_eu_tzone_hidden": "01/02/2020 02:23",
        "datetime_eu_tzone_visible": "01/02/2020 02:23",
        "datetime_us": "02/01/2020 01:23",
        "duration_dh": "1d 1h",
        "duration_dhm": "1d 1:01",
        "duration_dhms": "1d 1:01:06",
        "duration_hm": "1:01",
        "duration_hms": "1:01:06",
        "duration_hms_s": "1:01:06.6",
        "duration_hms_ss": "1:01:06.66",
        "duration_hms_sss": "1:01:06.666",
        "email": "test@example.com",
        "file": "a.txt, b.txt",
        "long_text": "long_text",
        "negative_decimal": "-1.2",
        "negative_int": "-1",
        "phone_number": "+4412345678",
        "positive_decimal": "1.2",
        "positive_int": "1",
        "rating": "3",
        "text": "text",
        "url": "https://www.google.com",
        "created_on_date_eu": "02/01/2021",
        "created_on_date_us": "01/02/2021",
        "created_on_datetime_eu": "02/01/2021 12:00",
        "created_on_datetime_us": "01/02/2021 12:00",
        "created_on_datetime_eu_tzone": "02/01/2021 13:00",
        "last_modified_date_eu": "02/01/2021",
        "last_modified_date_us": "01/02/2021",
        "last_modified_datetime_eu": "02/01/2021 12:00",
        "last_modified_datetime_us": "01/02/2021 12:00",
        "last_modified_datetime_eu_tzone": "02/01/2021 13:00",
        "autonumber": "2",
        "ai": "I'm an AI.",
        "uuid": "00000000-0000-4000-8000-000000000002",
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table_is_equal(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    source_table, user, *_ = setup_interesting_test_table(enterprise_data_fixture)
    source_fields = [
        field
        for field in specific_iterator(source_table.field_set.all())
        if field_type_registry.get_by_model(field).type
        in BaserowFieldDataSyncProperty.supported_field_types
    ]

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    synced_properties = ["id"] + [f"field_{field.id}" for field in source_fields]

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=synced_properties,
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = model.objects.all()
    row_1 = rows[0]
    row_2 = rows[1]

    row_1_last_modified = row_1.updated_on
    row_2_last_modified = row_2.updated_on

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    row_1.refresh_from_db()
    row_2.refresh_from_db()

    # Because none of the values have changed in the source (interesting) table,
    # we don't expect the rows to have been updated. If they have been updated,
    # it means that the `is_equal` method of `BaserowFieldDataSyncProperty` is not
    # working as expected.
    assert row_1.updated_on == row_1_last_modified
    assert row_2.updated_on == row_2_last_modified


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_via_api_no_access_to_source_table(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    source_table = enterprise_data_fixture.create_database_table(name="Source")
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "local_baserow_table",
            "synced_properties": ["id"],
            "source_table_id": source_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_SYNC_ERROR"
    assert (
        response_json["detail"]
        == "The authorized user doesn't have access to the table."
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync_properties_source_table_does_not_exist(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "local_baserow_table",
            "source_table_id": 0,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_SYNC_ERROR"
    assert response_json["detail"] == "The source table doesn't exist."


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync_properties_no_access_to_source_table(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    source_table = enterprise_data_fixture.create_database_table(name="Source")

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "local_baserow_table",
            "source_table_id": source_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_SYNC_ERROR"
    assert (
        response_json["detail"]
        == "The authorized user doesn't have access to the table."
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_data_sync_properties(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    field_1 = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )
    field_2 = enterprise_data_fixture.create_number_field(
        table=source_table, name="Number", primary=False, number_decimal_places=2
    )

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "local_baserow_table",
            "source_table_id": source_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "id",
            "name": "Row ID",
            "field_type": "number",
        },
        {
            "unique_primary": False,
            "key": f"field_{field_1.id}",
            "name": "Text",
            "field_type": "text",
        },
        {
            "unique_primary": False,
            "key": f"field_{field_2.id}",
            "name": "Number",
            "field_type": "number",
        },
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_without_license(enterprise_data_fixture, api_client):
    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "local_baserow_table",
            "synced_properties": ["id"],
            "source_table_id": table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sync_data_sync_table_without_license(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id"],
        source_table_id=source_table.id,
    )

    License.objects.all().delete()

    with pytest.raises(FeaturesNotAvailableError):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_async_sync_data_sync_table_without_license(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "local_baserow_table",
            "synced_properties": ["id"],
            "source_table_id": source_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    data_sync_id = response.json()["data_sync"]["id"]

    License.objects.all().delete()

    response = api_client.post(
        reverse(
            "api:database:data_sync:sync_table", kwargs={"data_sync_id": data_sync_id}
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
