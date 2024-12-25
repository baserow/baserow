import math
from datetime import date, datetime
from decimal import Decimal

import requests
from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.data_sync.exceptions import SyncError
from baserow.contrib.database.data_sync.models import DataSyncSyncedProperty
from baserow.contrib.database.data_sync.registries import DataSyncProperty, DataSyncType
from baserow.contrib.database.data_sync.utils import (
    SourceOption,
    compare_date,
    update_baserow_field_select_options,
)
from baserow.contrib.database.fields.models import (
    DateField,
    Field,
    LongTextField,
    NumberField,
    PhoneNumberField,
    SingleSelectField,
    TextField,
)
from baserow.core.utils import ChildProgressBuilder, get_value_at_path
from baserow_enterprise.data_sync.models import HubSpotContactsDataSync
from baserow_enterprise.features import DATA_SYNC


class HubspotIDProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> Field:
        return NumberField(name=self.name)


class BaseHubspotProperty(DataSyncProperty):
    immutable_properties = True

    def __init__(self, hubspot_object):
        name = hubspot_object["name"]
        self.description = hubspot_object["description"]
        self.field_type = hubspot_object["fieldType"]
        self.options = hubspot_object["options"]
        return super().__init__(
            key=hubspot_object["name"],
            name=hubspot_object["label"],
            # Because there are so many properties, we only want to initially select
            # the ones about contactinformation and the non hubspot specific values.
            # This gives a good initial selection of relevant data. Everything else
            # can optionally be enabled by the user.
            initially_selected=(
                hubspot_object["groupName"] == "contactinformation"
                and "hs_" not in name
            ),
        )

    def prepare_value(self, value, metadata):
        return value


class HubspotStringProperty(BaseHubspotProperty):
    def to_baserow_field(self) -> Field:
        if self.field_type == "textarea":
            return LongTextField(name=self.name, description=self.description)
        if self.field_type == "phonenumber":
            return PhoneNumberField(name=self.name, description=self.description)
        else:
            return TextField(name=self.name, description=self.description)


class HubspotNumberProperty(BaseHubspotProperty):
    def to_baserow_field(self) -> Field:
        return NumberField(name=self.name, description=self.description)

    def is_equal(self, baserow_row_value, data_sync_row_value) -> bool:
        data_sync_row_value = (
            Decimal(data_sync_row_value) if data_sync_row_value else None
        )
        return super().is_equal(baserow_row_value, data_sync_row_value)


class HubspotDateProperty(BaseHubspotProperty):
    def to_baserow_field(self) -> Field:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=False,
            description=self.description,
        )

    def is_equal(self, baserow_row_value, data_sync_row_value) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)

    def prepare_value(self, value, metadata):
        try:
            return date.fromisoformat(value)
        except TypeError:
            return None


class HubspotDateTimeProperty(BaseHubspotProperty):
    def to_baserow_field(self) -> Field:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
            description=self.description,
        )

    def is_equal(self, baserow_row_value, data_sync_row_value) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)

    def prepare_value(self, value, metadata):
        try:
            return datetime.fromisoformat(value)
        except TypeError:
            return None


class HubspotEnumerationProperty(BaseHubspotProperty):
    def to_baserow_field(self) -> Field:
        return SingleSelectField(name=self.name, description=self.description)

    def prepare_value(self, value, metadata):
        if not value:
            return None

        mapping = metadata.get("select_options_mapping", {})
        return mapping.get(value, None)

    def get_metadata(self, baserow_field, existing_metadata=None):
        new_metadata = super().get_metadata(baserow_field, existing_metadata)

        if new_metadata is None:
            new_metadata = {}

        # Based on the existing mapping, we can figure out which select options must
        # be created, updated, and deleted in the synced field.
        existing_mapping = {}
        if existing_metadata:
            existing_mapping = existing_metadata.get("select_options_mapping", {})

        options = [
            SourceOption(
                id=option["value"],
                value=option["label"],
                color="light-blue",
                order=option["displayOrder"],
            )
            for option in self.options
        ]

        select_options_mapping = update_baserow_field_select_options(
            options,
            baserow_field,
            existing_mapping,
        )
        new_metadata["select_options_mapping"] = select_options_mapping

        return new_metadata

    def is_equal(self, baserow_row_value, data_sync_row_value) -> bool:
        return super().is_equal(baserow_row_value, data_sync_row_value)


hubspot_property_type_mapping = {
    "string": HubspotStringProperty,
    "phone_number": HubspotStringProperty,
    "number": HubspotNumberProperty,
    "date": HubspotDateProperty,
    "datetime": HubspotDateTimeProperty,
    "enumeration": HubspotEnumerationProperty,
}


class HubspotContactsDataSyncType(DataSyncType):
    type = "hubspot_contacts"
    model_class = HubSpotContactsDataSync
    allowed_fields = [
        "hubspot_access_token",
    ]
    request_serializer_field_names = [
        "hubspot_access_token",
    ]
    serializer_field_names = []
    base_url = "https://api.hubapi.com"

    def prepare_sync_job_values(self, instance):
        # Raise the error so that the job doesn't start and the user is informed with
        # the correct error.
        LicenseHandler.raise_if_workspace_doesnt_have_feature(
            DATA_SYNC, instance.table.database.workspace
        )

    def get_properties(self, instance):
        # The `table_id` is not set if when just listing the properties using the
        # `DataSyncPropertiesView` endpoint, but it will be set when creating the view.
        if instance.table_id:
            LicenseHandler.raise_if_workspace_doesnt_have_feature(
                DATA_SYNC, instance.table.database.workspace
            )

        try:
            # This endpoint responds with all the available contact properties and
            # their types. They can all be included in the response when fetching the
            # contacts.
            response = requests.get(
                f"{self.base_url}/crm/v3/properties/contacts?archived=false",
                headers={"Authorization": f"Bearer {instance.hubspot_access_token}"},
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise SyncError(f"Error fetching HubSpot properties: {str(e)}")

        fetched_properties = response.json()["results"]
        properties = [HubspotIDProperty(key="id", name="Contact ID")]
        properties = properties + [
            hubspot_property_type_mapping.get(property_object["type"])(
                hubspot_object=property_object
            )
            for property_object in fetched_properties
            if property_object["type"] in hubspot_property_type_mapping.keys()
        ]
        return properties

    def get_contact_count(self, instance, headers):
        try:
            response = requests.post(
                f"{self.base_url}/crm/v3/objects/contacts/search",
                headers=headers,
                timeout=10,
                json={"filterGroups": [], "limit": 0},
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise SyncError(f"Error fetching HubSpot contacts: {str(e)}")

        return response.json()["total"]

    def get_all_rows(self, instance, progress_builder=None):
        properties = self.get_properties(instance)
        synced_properties = DataSyncSyncedProperty.objects.filter(data_sync=instance)
        synced_property_keys = [p.key for p in synced_properties]

        headers = {"Authorization": f"Bearer {instance.hubspot_access_token}"}
        page_limit = 50
        contact_count = self.get_contact_count(instance, headers)
        page_count = math.ceil(contact_count / page_limit)

        progress = ChildProgressBuilder.build(
            progress_builder,
            child_total=page_count + 1,
        )
        progress.increment(by=1)

        all_contacts = []
        query_params = {
            "limit": page_limit,
            "archived": "false",
            "properties": synced_property_keys,
        }

        while True:
            url = f"{self.base_url}/crm/v3/objects/contacts"

            try:
                response = requests.get(
                    url, headers=headers, params=query_params, timeout=10
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                raise SyncError(f"Error fetching HubSpot contacts: {str(e)}")

            data = response.json()
            all_contacts.extend(data.get("results", []))

            progress.increment(by=1)

            # If `after` is not in the response, or if it's `None`, then there is no
            # consecutive page, and we can stop the loop.
            after = get_value_at_path(data, "paging.next.after", None)
            if after:
                query_params["after"] = after
            else:
                break

        rows = []
        for contact in all_contacts:
            row = {"id": Decimal(contact["id"])}
            for enabled_property in synced_properties:
                if enabled_property.key == "id":
                    continue

                property_instance = next(
                    p
                    for p in properties
                    if p.key != "id" and p.key == enabled_property.key
                )
                # The property type instance sometimes has to modify the value,
                # like with the `enumeration` type, it must be mapped to a select
                # option.
                row[enabled_property.key] = property_instance.prepare_value(
                    contact["properties"][enabled_property.key],
                    enabled_property.metadata,
                )
            rows.append(row)

        return rows
