import datetime
from copy import deepcopy
from decimal import Decimal

from django.test.utils import override_settings
from django.urls import reverse

import pytest
import responses
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.models import License
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.data_sync.handler import DataSyncHandler
from baserow.contrib.database.fields.models import NumberField
from baserow.core.db import specific_iterator
from baserow_enterprise.data_sync.models import HubSpotContactsDataSync

ALL_PROPERTIES_RESPONSE = {
    "results": [
        {
            "updatedAt": "2024-09-12T14:22:56.844Z",
            "createdAt": "2020-06-30T15:57:37.277Z",
            "name": "address",
            "label": "Street Address",
            "type": "string",
            "fieldType": "text",
            "description": "Contact's street address, including apartment or unit number.",
            "groupName": "contactinformation",
            "options": [],
            "displayOrder": 6,
            "calculated": False,
            "externalOptions": False,
            "hasUniqueValue": False,
            "hidden": False,
            "hubspotDefined": True,
            "modificationMetadata": {
                "archivable": True,
                "readOnlyDefinition": True,
                "readOnlyValue": False,
            },
            "formField": True,
            "dataSensitivity": "non_sensitive",
        },
        {
            "updatedAt": "2024-09-05T17:14:04.747Z",
            "createdAt": "2019-08-06T02:41:09.377Z",
            "name": "associatedcompanyid",
            "label": "Primary Associated Company ID",
            "type": "number",
            "fieldType": "number",
            "description": "HubSpot defined ID of a contact's primary associated company in HubSpot.",
            "groupName": "contactinformation",
            "options": [],
            "referencedObjectType": "COMPANY",
            "displayOrder": 24,
            "calculated": False,
            "externalOptions": True,
            "hasUniqueValue": False,
            "hidden": True,
            "hubspotDefined": True,
            "modificationMetadata": {
                "archivable": True,
                "readOnlyDefinition": True,
                "readOnlyValue": False,
            },
            "formField": False,
            "dataSensitivity": "non_sensitive",
        },
        {
            "updatedAt": "2024-09-05T17:14:04.747Z",
            "createdAt": "2019-08-06T02:41:09.148Z",
            "name": "createdate",
            "label": "Create Date",
            "type": "datetime",
            "fieldType": "date",
            "description": "The date that a contact entered the system",
            "groupName": "contactinformation",
            "options": [],
            "displayOrder": 17,
            "calculated": False,
            "externalOptions": False,
            "hasUniqueValue": False,
            "hidden": False,
            "hubspotDefined": True,
            "modificationMetadata": {
                "archivable": True,
                "readOnlyDefinition": True,
                "readOnlyValue": True,
            },
            "formField": False,
            "dataSensitivity": "non_sensitive",
        },
        {
            "updatedAt": "2024-09-05T17:14:04.747Z",
            "createdAt": "2019-08-06T02:41:09.148Z",
            "name": "date",
            "label": "Create Date",
            "type": "date",
            "fieldType": "date",
            "description": "Just a date",
            "groupName": "contactinformation",
            "options": [],
            "displayOrder": 17,
            "calculated": False,
            "externalOptions": False,
            "hasUniqueValue": False,
            "hidden": False,
            "hubspotDefined": True,
            "modificationMetadata": {
                "archivable": True,
                "readOnlyDefinition": True,
                "readOnlyValue": True,
            },
            "formField": False,
            "dataSensitivity": "non_sensitive",
        },
        {
            "updatedAt": "2024-09-06T20:46:08.884Z",
            "createdAt": "2020-06-30T15:57:37.247Z",
            "name": "currentlyinworkflow",
            "label": "Currently in workflow",
            "type": "enumeration",
            "fieldType": "booleancheckbox",
            "description": "True when contact is enrolled in a workflow.",
            "groupName": "contact_activity",
            "options": [
                {
                    "label": "True",
                    "value": "True",
                    "description": "",
                    "displayOrder": 0,
                    "hidden": False,
                },
                {
                    "label": "False",
                    "value": "False",
                    "description": "",
                    "displayOrder": 1,
                    "hidden": False,
                },
            ],
            "displayOrder": 1,
            "calculated": False,
            "externalOptions": False,
            "hasUniqueValue": False,
            "hidden": False,
            "hubspotDefined": True,
            "modificationMetadata": {
                "archivable": True,
                "readOnlyDefinition": True,
                "readOnlyValue": True,
            },
            "formField": False,
            "dataSensitivity": "non_sensitive",
        },
    ]
}

COUNT_RESPONSE = {"total": 2, "results": [], "paging": {"next": {"after": "0"}}}

CONTACT_1 = {
    "id": "1",
    "properties": {
        "address": "Test address",
        "associatedcompanyid": "1",
        "createdate": "2020-06-30T15:57:37.247Z",
        "date": "2020-06-30",
        "currentlyinworkflow": "True",
    },
    "createdAt": "2024-11-26T19:19:01.258Z",
    "updatedAt": "2024-11-26T19:19:09.765Z",
    "archived": False,
}

CONTACT_2 = {
    "id": "2",
    "properties": {
        "address": "Some address",
        "associatedcompanyid": "2",
        "createdate": "2020-06-29T15:57:37.247Z",
        "date": "2020-06-28",
        "currentlyinworkflow": "False",
    },
    "createdAt": "2024-11-26T19:19:01.258Z",
    "updatedAt": "2024-11-26T19:19:09.765Z",
    "archived": False,
}


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="hubspot_contacts",
        synced_properties=[
            "id",
            "address",
            "associatedcompanyid",
            "createdate",
            "date",
            "currentlyinworkflow",
        ],
        hubspot_access_token="test",
    )

    assert isinstance(data_sync, HubSpotContactsDataSync)
    assert data_sync.hubspot_access_token == "test"

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    assert len(fields) == 6
    assert fields[0].name == "Contact ID"
    assert isinstance(fields[0], NumberField)
    assert fields[0].primary is True
    assert fields[0].read_only is True
    assert fields[0].immutable_type is True
    assert fields[0].immutable_properties is True
    assert fields[0].number_decimal_places == 0
    assert fields[1].name == "Street Address"
    assert fields[1].primary is False
    assert fields[1].read_only is True
    assert fields[1].immutable_type is True
    assert fields[1].immutable_properties is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )
    responses.add(
        responses.POST,
        "https://api.hubapi.com/crm/v3/objects/contacts/search",
        status=200,
        json=COUNT_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/objects/contacts",
        status=200,
        json={"results": [CONTACT_1, CONTACT_2]},
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="hubspot_contacts",
        synced_properties=[
            "id",
            "address",
            "associatedcompanyid",
            "createdate",
            "date",
            "currentlyinworkflow",
        ],
        hubspot_access_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    data_sync.refresh_from_db()

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    contact_id_field = fields[0]
    address_field = fields[1]
    associatedcompanyid_field = fields[2]
    createdate_field = fields[3]
    date_field = fields[4]
    currentlyinworkflow_field = fields[5]

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 2
    row = model.objects.all().first()

    assert getattr(row, f"field_{contact_id_field.id}") == Decimal("1")
    assert getattr(row, f"field_{address_field.id}") == "Test address"
    assert getattr(row, f"field_{associatedcompanyid_field.id}") == Decimal("1")
    assert getattr(row, f"field_{createdate_field.id}") == datetime.datetime(
        2020, 6, 30, 15, 57, 37, 247000, tzinfo=datetime.timezone.utc
    )
    assert getattr(row, f"field_{date_field.id}") == datetime.date(2020, 6, 30)
    assert getattr(row, f"field_{currentlyinworkflow_field.id}").value == "True"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_pagination(enterprise_data_fixture):
    count_response = deepcopy(COUNT_RESPONSE)
    count_response["total"] = 51

    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )
    responses.add(
        responses.POST,
        "https://api.hubapi.com/crm/v3/objects/contacts/search",
        status=200,
        json=count_response,
    )
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/objects/contacts?limit=50&archived=false&properties=id",
        status=200,
        json={"results": [CONTACT_1], "paging": {"next": {"after": "1"}}},
    )
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/objects/contacts?limit=50&archived=false&properties=id&after=1",
        status=200,
        json={"results": [CONTACT_2]},
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="hubspot_contacts",
        synced_properties=[
            "id",
        ],
        hubspot_access_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    assert model.objects.all().count() == 2

    fields = specific_iterator(data_sync.table.field_set.all().order_by("id"))
    contact_id_field = fields[0]

    rows = model.objects.all()
    assert rows[0]

    assert getattr(rows[0], f"field_{contact_id_field.id}") == Decimal("1")
    assert getattr(rows[1], f"field_{contact_id_field.id}") == Decimal("2")


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_is_equal(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )
    responses.add(
        responses.POST,
        "https://api.hubapi.com/crm/v3/objects/contacts/search",
        status=200,
        json=COUNT_RESPONSE,
    )
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/objects/contacts",
        status=200,
        json={"results": [CONTACT_1, CONTACT_2]},
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="hubspot_contacts",
        synced_properties=[
            "id",
            "address",
            "associatedcompanyid",
            "createdate",
            "date",
            "currentlyinworkflow",
        ],
        hubspot_access_token="test",
    )
    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    model = data_sync.table.get_model()
    rows = model.objects.all()
    row_1 = rows[0]
    row_2 = rows[1]

    row_1_last_modified = row_1.updated_on
    row_2_last_modified = row_2.updated_on

    handler.sync_data_sync_table(user=user, data_sync=data_sync)

    rows = model.objects.all()
    row_1 = rows[0]
    row_2 = rows[1]

    # Because none of the values have changed, we don't expect the rows to have been
    # updated.
    assert row_1.updated_on == row_1_last_modified
    assert row_2.updated_on == row_2_last_modified


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_table_invalid_access_token(
    enterprise_data_fixture, api_client
):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=401,
        json={
            "status": "error",
            "message": "Authentication credentials not found. This API supports OAuth 2.0 authentication and you can find more details at https://developers.hubspot.com/docs/methods/auth/oauth-overview",
            "correlationId": "ID",
            "category": "INVALID_AUTHENTICATION",
        },
    )

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "hubspot_contacts",
            "hubspot_access_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_SYNC_ERROR"
    assert (
        response_json["detail"]
        == "Error fetching HubSpot properties: 401 Client Error: Unauthorized for url: https://api.hubapi.com/crm/v3/properties/contacts?archived=false"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_get_data_sync_properties(enterprise_data_fixture, api_client):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()
    user, token = enterprise_data_fixture.create_user_and_token()

    url = reverse("api:database:data_sync:properties")
    response = api_client.post(
        url,
        {
            "type": "hubspot_contacts",
            "hubspot_access_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "unique_primary": True,
            "key": "id",
            "name": "Contact ID",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "address",
            "name": "Street Address",
            "field_type": "text",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "associatedcompanyid",
            "name": "Primary Associated Company ID",
            "field_type": "number",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "createdate",
            "name": "Create Date",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "date",
            "name": "Create Date",
            "field_type": "date",
            "initially_selected": True,
        },
        {
            "unique_primary": False,
            "key": "currentlyinworkflow",
            "name": "Currently in workflow",
            "field_type": "single_select",
            "initially_selected": False,
        },
    ]


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_create_data_sync_without_license(enterprise_data_fixture, api_client):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )

    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "hubspot_contacts",
            "synced_properties": ["id"],
            "hubspot_access_token": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_sync_data_sync_table_without_license(enterprise_data_fixture):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()

    database = enterprise_data_fixture.create_database_application(user=user)
    handler = DataSyncHandler()

    data_sync = handler.create_data_sync_table(
        user=user,
        database=database,
        table_name="Test",
        type_name="hubspot_contacts",
        synced_properties=["id"],
        hubspot_access_token="test",
    )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        handler.sync_data_sync_table(user=user, data_sync=data_sync)


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@responses.activate
def test_async_sync_data_sync_table_without_license(
    api_client, enterprise_data_fixture, synced_roles
):
    responses.add(
        responses.GET,
        "https://api.hubapi.com/crm/v3/properties/contacts?archived=false",
        status=200,
        json=ALL_PROPERTIES_RESPONSE,
    )

    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    database = enterprise_data_fixture.create_database_application(user=user)

    url = reverse("api:database:data_sync:list", kwargs={"database_id": database.id})
    response = api_client.post(
        url,
        {
            "table_name": "Test 1",
            "type": "hubspot_contacts",
            "synced_properties": ["id"],
            "hubspot_access_token": "test",
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
