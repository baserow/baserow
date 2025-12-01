from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, transaction
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext, override_settings

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
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.db import specific_iterator
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.test_utils.helpers import setup_interesting_test_table
from baserow_enterprise.data_sync.baserow_table_data_sync import (
    BaserowFieldDataSyncProperty,
    supported_field_types,
)
from baserow_enterprise.data_sync.models import LocalBaserowTableDataSync


@pytest.mark.django_db
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_authorized_user_is_none(enterprise_data_fixture):
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
        authorized_user=None,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.authorized_user_id == user.id


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_authorized_user_is_set(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user_2 = enterprise_data_fixture.create_user()

    workspace = enterprise_data_fixture.create_workspace(users=[user_2, user])

    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    source_table = enterprise_data_fixture.create_database_table(
        database=database, name="Source"
    )

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id"],
        source_table_id=source_table.id,
        authorized_user=user,
    )
    handler.sync_data_sync_table(user=user_2, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.authorized_user_id == user.id


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_with_interesting_table_as_source(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    source_table, user, *_ = setup_interesting_test_table(enterprise_data_fixture)
    source_fields = [
        field
        for field in specific_iterator(source_table.field_set.all())
        if field_type_registry.get_by_model(field).type in supported_field_types
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
        "boolean_with_default": "True",
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
        "decimal_with_default": "1.8",
        "rating": "0",
        "single_select": "",
        "single_select_with_default": "BB",
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
        "ai_choice": "",
        "uuid": "00000000-0000-4000-8000-000000000001",
    }
    assert results == {
        "Row ID": "2",
        "boolean": "True",
        "boolean_with_default": "True",
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
        "decimal_with_default": "1.8",
        "rating": "3",
        "single_select": "A",
        "single_select_with_default": "BB",
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
        "ai_choice": "Object",
        "uuid": "00000000-0000-4000-8000-000000000002",
    }


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_is_equal(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    source_table, user, *_ = setup_interesting_test_table(enterprise_data_fixture)
    source_fields = [
        field
        for field in specific_iterator(source_table.field_set.all())
        if field_type_registry.get_by_model(field).type in supported_field_types
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
@pytest.mark.data_sync
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
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": f"field_{field_1.id}",
            "name": "Text",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": f"field_{field_2.id}",
            "name": "Number",
            "field_type": "number",
            "initially_selected": True,
        },
    ]


@pytest.mark.django_db
@pytest.mark.data_sync
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

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_async_sync_data_sync_table_without_license(
    api_client, enterprise_data_fixture, synced_roles
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


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_import_export_including_source_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    source_table = enterprise_data_fixture.create_database_table(
        name="Source", database=database
    )
    text_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text"
    )

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{text_field.id}"],
        source_table_id=source_table.id,
    )
    properties = data_sync.synced_properties.all().order_by("key")
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    imported_workspace = enterprise_data_fixture.create_workspace()
    imported_workspace_user = enterprise_data_fixture.create_user_workspace(
        workspace=imported_workspace, user=user
    )
    id_mapping = {}

    imported_database = database_type.import_serialized(
        imported_workspace,
        serialized,
        config,
        id_mapping,
        None,
        None,
    )

    imported_table = imported_database.table_set.filter(name="Test").first()
    imported_source_table = imported_database.table_set.filter(name="Source").first()
    imported_data_sync = imported_table.data_sync.specific
    imported_text_field = imported_source_table.field_set.all().first()

    assert imported_data_sync.authorized_user_id is None

    assert imported_data_sync.source_table_id == imported_source_table.id
    fields = imported_data_sync.table.field_set.all().order_by("id")
    assert fields[0].read_only is True
    assert fields[1].read_only is True

    imported_properties = imported_data_sync.synced_properties.all().order_by("key")
    assert imported_properties[0].key != f"field_{text_field.id}"
    assert imported_properties[0].key == f"field_{imported_text_field.id}"
    assert imported_properties[1].key == "id"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_import_export_duplicate_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    source_table = enterprise_data_fixture.create_database_table(
        name="Source", database=database
    )
    text_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text"
    )

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{text_field.id}"],
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    duplicated_table = TableHandler().duplicate_table(user, data_sync.table)
    assert duplicated_table.id != data_sync.table_id

    imported_data_sync = duplicated_table.data_sync.specific
    assert imported_data_sync.source_table_id == data_sync.source_table_id
    assert imported_data_sync.authorized_user_id is None

    assert imported_data_sync.authorized_user_id is None

    fields = imported_data_sync.table.field_set.all().order_by("id")
    assert fields[0].read_only is True
    assert fields[1].read_only is True

    imported_properties = imported_data_sync.synced_properties.all().order_by("key")
    assert imported_properties[0].key == f"field_{text_field.id}"
    assert imported_properties[1].key == "id"


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_import_export_excluding_source_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user)
    workspace_2 = enterprise_data_fixture.create_workspace(user=user)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    database_2 = enterprise_data_fixture.create_database_application(
        workspace=workspace_2
    )
    source_table = enterprise_data_fixture.create_database_table(
        name="Source", database=database_2
    )
    text_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text"
    )

    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{text_field.id}"],
        source_table_id=source_table.id,
    )
    properties = data_sync.synced_properties.all().order_by("key")
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(database, config)

    imported_workspace = enterprise_data_fixture.create_workspace()
    imported_workspace_user = enterprise_data_fixture.create_user_workspace(
        workspace=imported_workspace, user=user
    )
    id_mapping = {}

    imported_database = database_type.import_serialized(
        imported_workspace,
        serialized,
        config,
        id_mapping,
        None,
        None,
    )

    imported_table = imported_database.table_set.filter(name="Test").first()
    with pytest.raises(ObjectDoesNotExist):
        imported_table.data_sync

    fields = imported_table.field_set.all().order_by("id")
    assert fields[0].read_only is False
    assert fields[0].immutable_properties is False
    assert fields[0].immutable_type is False
    assert fields[1].read_only is False
    assert fields[1].immutable_properties is False
    assert fields[1].immutable_type is False


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_single_select_field(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    source_single_select_field = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )
    source_option_a = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="A", color="blue"
    )
    source_option_b = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="B", color="red"
    )

    source_model = source_table.get_model()
    source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}_id": source_option_a.id,
        }
    )
    source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}_id": source_option_b.id,
        }
    )
    source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}": None,
        }
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{source_single_select_field.id}"],
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    row_id_field = fields[0]
    single_select_field = fields[1]
    options = single_select_field.select_options.all()

    assert single_select_field.read_only is True
    assert single_select_field.immutable_type is True
    assert single_select_field.immutable_properties is True

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 3

    row_a = rows[0]
    row_b = rows[1]
    row_empty = rows[2]
    assert getattr(row_a, f"field_{single_select_field.id}_id") == options[0].id
    assert getattr(row_b, f"field_{single_select_field.id}_id") == options[1].id
    assert getattr(row_empty, f"field_{single_select_field.id}_id") is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_single_select_field_and_making_changes(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    source_single_select_field = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )
    source_option_a = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="A", color="blue"
    )
    source_option_b = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="B", color="red"
    )

    source_model = source_table.get_model()
    source_row_a = source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}_id": source_option_a.id,
        }
    )
    source_row_b = source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}_id": source_option_b.id,
        }
    )
    source_row_b_2 = source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}_id": source_option_b.id,
        }
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{source_single_select_field.id}"],
        source_table_id=source_table.id,
    )
    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    source_option_b.delete()
    source_option_c = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="C", color="orange"
    )

    setattr(
        source_row_b_2, f"field_{source_single_select_field.id}_id", source_option_c.id
    )
    source_row_b_2.save()
    source_row_c = source_model.objects.create(
        **{
            f"field_{source_single_select_field.id}_id": source_option_c.id,
        }
    )

    print("LAST")
    with transaction.atomic():
        handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    row_id_field = fields[0]
    single_select_field = fields[1]
    options = single_select_field.select_options.all()

    assert options[0].value == "A"
    assert options[1].value == "C"

    model = data_sync.table.get_model()
    rows = list(model.objects.all())
    assert len(rows) == 4

    row_a = rows[0]
    row_b = rows[1]
    row_b_2 = rows[2]
    row_c = rows[3]
    assert getattr(row_a, f"field_{single_select_field.id}_id") == options[0].id
    assert getattr(row_b, f"field_{single_select_field.id}_id") is None
    assert getattr(row_b_2, f"field_{single_select_field.id}_id") == options[1].id
    assert getattr(row_c, f"field_{single_select_field.id}_id") == options[1].id


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_single_select_get_metadata_create(
    enterprise_data_fixture, django_assert_num_queries
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    source_single_select_field = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )
    source_option_a = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="A", color="blue"
    )
    source_option_b = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="B", color="red"
    )

    target_single_select_field_1 = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )

    data_sync_property = BaserowFieldDataSyncProperty(
        field=source_single_select_field,
        immutable_properties=False,
        name="name",
        key="field",
    )

    with django_assert_num_queries(2):
        metadata = data_sync_property.get_metadata(target_single_select_field_1)

    target_select_options = list(target_single_select_field_1.select_options.all())
    assert len(target_select_options) == 2

    assert target_select_options[0].value == "A"
    assert target_select_options[0].color == "blue"
    assert target_select_options[1].value == "B"
    assert target_select_options[1].color == "red"

    assert metadata == {
        "select_options_mapping": {
            str(source_option_a.id): target_select_options[0].id,
            str(source_option_b.id): target_select_options[1].id,
        }
    }


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_single_select_get_metadata_update(
    enterprise_data_fixture, django_assert_num_queries
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    source_single_select_field = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )
    source_option_a = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="A", color="blue"
    )
    source_option_b = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="B", color="red"
    )

    target_single_select_field_1 = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )

    data_sync_property = BaserowFieldDataSyncProperty(
        field=source_single_select_field,
        immutable_properties=False,
        name="name",
        key="field",
    )
    metadata = data_sync_property.get_metadata(target_single_select_field_1)

    target_select_options_old = list(target_single_select_field_1.select_options.all())

    source_option_a.value = "C"
    source_option_a.save()
    source_option_b.value = "D"
    source_option_b.save()

    data_sync_property = BaserowFieldDataSyncProperty(
        field=source_single_select_field,
        immutable_properties=False,
        name="name",
        key="field",
    )
    with django_assert_num_queries(2):
        metadata = data_sync_property.get_metadata(
            target_single_select_field_1, metadata
        )

    target_select_options = list(target_single_select_field_1.select_options.all())
    assert len(target_select_options) == 2

    # The option must be updated, but the ID must stay the same as before because
    # it's an update.
    assert target_select_options[0].id == target_select_options_old[0].id
    assert target_select_options[0].value == "C"
    assert target_select_options[1].id == target_select_options_old[1].id
    assert target_select_options[1].value == "D"

    assert metadata == {
        "select_options_mapping": {
            str(source_option_a.id): target_select_options[0].id,
            str(source_option_b.id): target_select_options[1].id,
        }
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_single_select_get_metadata_delete(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    source_single_select_field = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )
    source_option_a = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="A", color="blue"
    )
    source_option_b = enterprise_data_fixture.create_select_option(
        field=source_single_select_field, value="B", color="red"
    )

    target_single_select_field_1 = enterprise_data_fixture.create_single_select_field(
        table=source_table, name="Single select"
    )

    data_sync_property = BaserowFieldDataSyncProperty(
        field=source_single_select_field,
        immutable_properties=False,
        name="name",
        key="field",
    )
    metadata = data_sync_property.get_metadata(target_single_select_field_1)

    source_option_a.delete()

    with CaptureQueriesContext(connection) as captured:
        metadata = data_sync_property.get_metadata(
            target_single_select_field_1, metadata
        )
    assert len([c["sql"] for c in captured if c["sql"] not in ["BEGIN", "COMMIT"]]) <= 6

    target_select_options = list(target_single_select_field_1.select_options.all())
    assert len(target_select_options) == 1

    assert target_select_options[0].value == "B"

    assert metadata == {
        "select_options_mapping": {str(source_option_b.id): target_select_options[0].id}
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_change_source_table_with_changing_synced_fields(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source", database=database
    )
    source_text_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text"
    )

    source_2_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source 2", database=database
    )
    source_2_text_field = enterprise_data_fixture.create_text_field(
        table=source_2_table, name="Text"
    )

    handler = DataSyncHandler()
    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{source_text_field.id}"],
        source_table_id=source_table.id,
    )

    url = reverse("api:database:data_sync:item", kwargs={"data_sync_id": data_sync.id})
    response = api_client.patch(
        url,
        {
            "source_table_id": source_2_table.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    # Expect the other field to be removed.
    assert len(response_json["synced_properties"]) == 1
    assert response_json["synced_properties"][0]["key"] == "id"


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_create_data_sync_view_does_not_exist(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError) as e:
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="local_baserow_table",
            synced_properties=["id"],
            source_table_id=source_table.id,
            source_table_view_id=0,
        )

    assert "does not exist" in str(e)


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_create_data_sync_view_does_not_belong_to_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    view = enterprise_data_fixture.create_grid_view()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    with pytest.raises(SyncError) as e:
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="local_baserow_table",
            synced_properties=["id"],
            source_table_id=source_table.id,
            source_table_view_id=view.id,
        )

    assert "does not exist" in str(e)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_data_sync_with_view_provided(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    public_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )

    grid = enterprise_data_fixture.create_grid_view(
        table=source_table, user=user, public=True, create_options=False
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{public_field.id}"],
        source_table_id=source_table.id,
        source_table_view_id=grid.id,
    )

    assert isinstance(data_sync, LocalBaserowTableDataSync)
    assert data_sync.source_table_id == source_table.id
    assert data_sync.authorized_user_id == user.id

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 2
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


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_get_properties_with_view_provided_only_public_fields(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    public_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )
    hidden_field = enterprise_data_fixture.create_text_field(
        table=source_table,
        name="Number",
        primary=False,
    )

    grid = enterprise_data_fixture.create_grid_view(
        table=source_table, user=user, public=True, create_options=False
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, hidden_field, hidden=True
    )

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "local_baserow_table",
            "source_table_id": source_table.id,
            "source_table_view_id": grid.id,
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
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": f"field_{public_field.id}",
            "name": "Text",
            "field_type": "text",
            "initially_selected": True,
        },
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_properties_with_table_view_id_none(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "local_baserow_table",
            "source_table_id": source_table.id,
            "source_table_view_id": None,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_sync_data_sync_table_with_view_provided_having_filter_and_sort(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    public_field = enterprise_data_fixture.create_text_field(
        table=source_table, name="Text", primary=True
    )

    grid = enterprise_data_fixture.create_grid_view(
        table=source_table, user=user, public=True, create_options=False
    )

    enterprise_data_fixture.create_grid_view_field_option(
        grid, public_field, hidden=False
    )
    enterprise_data_fixture.create_view_filter(
        view=grid, field=public_field, type="not_equal", value="B"
    )
    enterprise_data_fixture.create_view_sort(view=grid, field=public_field, order="ASC")

    source_model = source_table.get_model()
    source_row_1 = source_model.objects.create(
        **{
            f"field_{public_field.id}": "C",
        }
    )
    source_model.objects.create(
        **{
            f"field_{public_field.id}": "B",
        }
    )
    source_model.objects.create(
        **{
            f"field_{public_field.id}": "A",
        }
    )

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{public_field.id}"],
        source_table_id=source_table.id,
        source_table_view_id=grid.id,
    )

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    field_1_field = fields[1]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 2
    row = list(model.objects.all())
    assert getattr(row[0], f"field_{field_1_field.id}") == "A"
    assert getattr(row[1], f"field_{field_1_field.id}") == "C"


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_source_table_view_deleted(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )

    grid = enterprise_data_fixture.create_grid_view(
        table=source_table, user=user, public=True, create_options=False
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
        source_table_view_id=grid.id,
    )

    grid_id = grid.id
    grid.delete()

    with pytest.raises(SyncError) as e:
        handler.create_data_sync_table(
            user=user,
            database=database,
            table_name="Test",
            type_name="local_baserow_table",
            synced_properties=["id"],
            source_table_id=source_table.id,
            source_table_view_id=grid.id,
        )

    assert "does not exist" in str(e)

    data_sync.refresh_from_db()
    # We expect the view to still exist so that it fails because if it's set to
    # `null`, it might expose all table data.
    assert data_sync.source_table_view_id == grid_id


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_table_with_trashed_synced_field(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()

    source_table = enterprise_data_fixture.create_database_table(
        user=user, name="Source"
    )
    source_text_field = enterprise_data_fixture.create_text_field(table=source_table)
    source_table.get_model().objects.create()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="local_baserow_table",
        synced_properties=["id", f"field_{source_text_field.id}"],
        source_table_id=source_table.id,
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    FieldHandler().delete_field(user, fields[1])

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()
    assert data_sync.last_error is None


@pytest.mark.django_db
@pytest.mark.data_sync
@override_settings(DEBUG=True)
def test_table_model_is_data_synced_table(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    database = enterprise_data_fixture.create_database_application(user=user)
    source_for_synced_table = enterprise_data_fixture.create_database_table(
        database=database, name="Synced"
    )
    table_with_no_synced_table = enterprise_data_fixture.create_database_table(
        database=database, name="Table"
    )

    data_sync = DataSyncHandler().create_data_sync_table(
        user=user,
        database=database,
        table_name="Source synced",
        type_name="local_baserow_table",
        synced_properties=["id"],
        source_table_id=source_for_synced_table.id,
    )

    assert data_sync.table.is_data_synced_table
    assert not table_with_no_synced_table.is_data_synced_table
