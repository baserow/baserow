from unittest.mock import Mock

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowGetRowUserServiceType,
    LocalBaserowListRowsUserServiceType,
    LocalBaserowServiceType,
    LocalBaserowTableServiceType,
)
from baserow.core.services.exceptions import ServiceImproperlyConfigured
from baserow.test_utils.helpers import setup_interesting_test_table
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_local_baserow_table_service_before_dispatch_validation_error(
    data_fixture,
):
    cls = LocalBaserowTableServiceType
    cls.model_class = Mock()

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trashed_table = data_fixture.create_database_table(
        user, database=database, trashed=True
    )
    trashed_database = data_fixture.create_database_application(
        workspace=workspace, trashed=True
    )
    table_in_trashed_database = data_fixture.create_database_table(
        user, database=trashed_database
    )

    service_without_table = Mock(table_id=None)
    dispatch_context = FakeDispatchContext()
    with pytest.raises(ServiceImproperlyConfigured) as exc:
        cls().resolve_service_formulas(service_without_table, dispatch_context)
    assert exc.value.args[0] == "The table property is missing."

    service_with_trashed_table = Mock(table_id=trashed_table.id)
    with pytest.raises(ServiceImproperlyConfigured) as exc:
        cls().resolve_service_formulas(service_with_trashed_table, dispatch_context)
    assert exc.value.args[0] == "The specified table is trashed"

    service_with_table_in_trashed_database = Mock(table_id=table_in_trashed_database.id)
    with pytest.raises(ServiceImproperlyConfigured) as exc:
        cls().resolve_service_formulas(
            service_with_table_in_trashed_database, dispatch_context
        )
    assert exc.value.args[0] == "The specified table is trashed"


@pytest.mark.django_db
def test_local_baserow_table_service_generate_schema_with_no_table(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )

    get_row_service_type = LocalBaserowGetRowUserServiceType()
    get_row_service = data_fixture.create_local_baserow_get_row_service(
        integration=integration
    )
    assert get_row_service_type.generate_schema(get_row_service) is None

    list_rows_service_type = LocalBaserowListRowsUserServiceType()
    list_rows_service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration
    )
    assert list_rows_service_type.generate_schema(list_rows_service) is None


@pytest.mark.django_db
def test_local_baserow_table_service_generate_schema_with_interesting_test_table(
    data_fixture,
):
    def reset_metadata(schema, field_name):
        # Responsible for resetting a schema's `metadata`,
        # it's simply a nested serialized field. Clearing it makes
        # testing this much simpler.
        for field_id, obj in schema[field_name].items():
            obj["metadata"] = {}

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    table, _, _, _, _ = setup_interesting_test_table(
        data_fixture,
        user,
    )
    field_db_column_by_name = {
        field.name: field.db_column for field in table.field_set.all()
    }
    expected_local_baserow_table_service_schema_fields = {
        field_db_column_by_name["text"]: {
            "title": "text",
            "default": "",
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "text",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["long_text"]: {
            "title": "long_text",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "long_text",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["url"]: {
            "title": "url",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "url",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["email"]: {
            "title": "email",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "email",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["negative_int"]: {
            "title": "negative_int",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "number",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["positive_int"]: {
            "title": "positive_int",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "number",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["negative_decimal"]: {
            "title": "negative_decimal",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "number",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["positive_decimal"]: {
            "title": "positive_decimal",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "number",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["rating"]: {
            "title": "rating",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "rating",
            "metadata": {},
            "type": "number",
        },
        field_db_column_by_name["boolean"]: {
            "title": "boolean",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "boolean",
            "metadata": {},
            "type": "boolean",
        },
        field_db_column_by_name["datetime_us"]: {
            "title": "datetime_us",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "date",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["date_us"]: {
            "title": "date_us",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "date",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["datetime_eu"]: {
            "title": "datetime_eu",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "date",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["date_eu"]: {
            "title": "date_eu",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "date",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["datetime_eu_tzone_visible"]: {
            "title": "datetime_eu_tzone_visible",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "date",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["datetime_eu_tzone_hidden"]: {
            "title": "datetime_eu_tzone_hidden",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "date",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["last_modified_datetime_us"]: {
            "title": "last_modified_datetime_us",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "last_modified",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["last_modified_date_us"]: {
            "title": "last_modified_date_us",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "last_modified",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["last_modified_datetime_eu"]: {
            "title": "last_modified_datetime_eu",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "last_modified",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["last_modified_date_eu"]: {
            "title": "last_modified_date_eu",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "last_modified",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["last_modified_datetime_eu_tzone"]: {
            "title": "last_modified_datetime_eu_tzone",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "last_modified",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["created_on_datetime_us"]: {
            "title": "created_on_datetime_us",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "created_on",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["created_on_date_us"]: {
            "title": "created_on_date_us",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "created_on",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["created_on_datetime_eu"]: {
            "title": "created_on_datetime_eu",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "created_on",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["created_on_date_eu"]: {
            "title": "created_on_date_eu",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "created_on",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["created_on_datetime_eu_tzone"]: {
            "title": "created_on_datetime_eu_tzone",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "created_on",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["last_modified_by"]: {
            "default": None,
            "metadata": {},
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "last_modified_by",
            "properties": {
                "id": {"title": "id", "type": "number"},
                "name": {"title": "name", "type": "string"},
            },
            "title": "last_modified_by",
            "type": "object",
        },
        field_db_column_by_name["created_by"]: {
            "default": None,
            "metadata": {},
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "created_by",
            "properties": {
                "id": {"title": "id", "type": "number"},
                "name": {"title": "name", "type": "string"},
            },
            "title": "created_by",
            "type": "object",
        },
        field_db_column_by_name["link_row"]: {
            "title": "link_row",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": True,
            "original_type": "link_row",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                },
            },
        },
        field_db_column_by_name["self_link_row"]: {
            "title": "self_link_row",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": True,
            "original_type": "link_row",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                },
            },
        },
        field_db_column_by_name["link_row_without_related"]: {
            "title": "link_row_without_related",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": True,
            "original_type": "link_row",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                },
            },
        },
        field_db_column_by_name["decimal_link_row"]: {
            "title": "decimal_link_row",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": True,
            "original_type": "link_row",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                },
            },
        },
        field_db_column_by_name["file_link_row"]: {
            "title": "file_link_row",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": True,
            "original_type": "link_row",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                },
            },
        },
        field_db_column_by_name["file"]: {
            "title": "file",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "file",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"title": "url", "type": "string"},
                    "visible_name": {"title": "visible_name", "type": "string"},
                    "name": {"title": "name", "type": "string"},
                    "size": {"title": "size", "type": "number"},
                    "mime_type": {"title": "mime_type", "type": "string"},
                    "is_image": {"title": "is_image", "type": "boolean"},
                    "image_width": {"title": "image_width", "type": "number"},
                    "image_height": {"title": "image_height", "type": "number"},
                    "uploaded_at": {"title": "uploaded_at", "type": "string"},
                },
            },
        },
        field_db_column_by_name["single_select"]: {
            "title": "single_select",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "single_select",
            "metadata": {},
            "type": "object",
            "properties": {
                "id": {"title": "id", "type": "number"},
                "value": {"title": "value", "type": "string"},
                "color": {"title": "color", "type": "string"},
            },
        },
        field_db_column_by_name["multiple_select"]: {
            "title": "multiple_select",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "multiple_select",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                    "color": {"title": "color", "type": "string"},
                },
            },
        },
        field_db_column_by_name["multiple_collaborators"]: {
            "title": "multiple_collaborators",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "multiple_collaborators",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "name": {"title": "name", "type": "string"},
                },
            },
        },
        field_db_column_by_name["phone_number"]: {
            "title": "phone_number",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "phone_number",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_text"]: {
            "title": "formula_text",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_int"]: {
            "title": "formula_int",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_bool"]: {
            "title": "formula_bool",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "boolean",
        },
        field_db_column_by_name["formula_decimal"]: {
            "title": "formula_decimal",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_dateinterval"]: {
            "title": "formula_dateinterval",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_date"]: {
            "title": "formula_date",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_singleselect"]: {
            "title": "formula_singleselect",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "object",
            "properties": {
                "id": {"title": "id", "type": "number"},
                "value": {"title": "value", "type": "string"},
                "color": {"title": "color", "type": "string"},
            },
        },
        field_db_column_by_name["formula_email"]: {
            "title": "formula_email",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["formula_link_with_label"]: {
            "title": "formula_link_with_label",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "object",
            "properties": {
                "url": {"title": "url", "type": "string"},
                "label": {"title": "label", "type": "string"},
            },
        },
        field_db_column_by_name["formula_link_url_only"]: {
            "title": "formula_link_url_only",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "object",
            "properties": {
                "url": {"title": "url", "type": "string"},
                "label": {"title": "label", "type": "string"},
            },
        },
        field_db_column_by_name["formula_multipleselect"]: {
            "title": "formula_multipleselect",
            "default": None,
            "searchable": True,
            "sortable": False,
            "filterable": False,
            "original_type": "formula",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                    "color": {"title": "color", "type": "string"},
                },
            },
        },
        field_db_column_by_name["count"]: {
            "title": "count",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "count",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["rollup"]: {
            "title": "rollup",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "rollup",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_rollup_sum"]: {
            "default": None,
            "metadata": {},
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "rollup",
            "title": "duration_rollup_sum",
            "type": "string",
        },
        field_db_column_by_name["duration_rollup_avg"]: {
            "default": None,
            "metadata": {},
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "rollup",
            "title": "duration_rollup_avg",
            "type": "string",
        },
        field_db_column_by_name["lookup"]: {
            "title": "lookup",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "lookup",
            "metadata": {},
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"title": "id", "type": "number"},
                    "value": {"title": "value", "type": "string"},
                },
            },
        },
        field_db_column_by_name["uuid"]: {
            "title": "uuid",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "uuid",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["autonumber"]: {
            "title": "autonumber",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "autonumber",
            "metadata": {},
            "type": "number",
        },
        field_db_column_by_name["duration_hm"]: {
            "title": "duration_hm",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_hms"]: {
            "title": "duration_hms",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_hms_s"]: {
            "title": "duration_hms_s",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_hms_ss"]: {
            "title": "duration_hms_ss",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_hms_sss"]: {
            "title": "duration_hms_sss",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_dh"]: {
            "title": "duration_dh",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_dhm"]: {
            "title": "duration_dhm",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["duration_dhms"]: {
            "title": "duration_dhms",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": True,
            "original_type": "duration",
            "metadata": {},
            "type": "string",
        },
        field_db_column_by_name["password"]: {
            "title": "password",
            "default": None,
            "searchable": False,
            "sortable": False,
            "filterable": True,  # Only by `EmptyViewFilterType`
            "original_type": "password",
            "metadata": {},
            "type": "boolean",
        },
        field_db_column_by_name["ai"]: {
            "title": "ai",
            "default": None,
            "searchable": True,
            "sortable": True,
            "filterable": False,
            "original_type": "ai",
            "metadata": {},
            "type": "string",
        },
        "id": {
            "type": "number",
            "title": "Id",
            "metadata": {},
            "sortable": True,
            "filterable": False,
            "searchable": False,
        },
    }

    get_row_service_type = LocalBaserowGetRowUserServiceType()
    get_row_service = data_fixture.create_local_baserow_get_row_service(
        integration=integration, table=table
    )
    get_row_schema = get_row_service_type.generate_schema((get_row_service))
    reset_metadata(get_row_schema, "properties")

    assert get_row_schema["type"] == "object"
    assert (
        get_row_schema["properties"]
        == expected_local_baserow_table_service_schema_fields
    )

    list_rows_service_type = LocalBaserowListRowsUserServiceType()
    list_rows_service = data_fixture.create_local_baserow_list_rows_service(
        integration=integration, table=table
    )
    list_rows_schema = list_rows_service_type.generate_schema(list_rows_service)
    reset_metadata(list_rows_schema["items"], "properties")

    assert list_rows_schema["type"] == "array"
    assert (
        list_rows_schema["items"]["properties"]
        == expected_local_baserow_table_service_schema_fields
    )


def test_local_baserow_service_type_get_schema_for_return_type():
    mock_service = Mock(id=123)
    cls = LocalBaserowServiceType
    cls.model_class = Mock()
    properties = {"1": {"field": "value"}}

    cls.returns_list = True
    assert cls().get_schema_for_return_type(mock_service, properties) == {
        "type": "array",
        "items": {"properties": properties, "type": "object"},
        "title": "Service123Schema",
    }

    cls.returns_list = False
    assert cls().get_schema_for_return_type(mock_service, properties) == {
        "type": "object",
        "properties": properties,
        "title": "Service123Schema",
    }


def test_local_baserow_table_service_type_schema_name():
    mock_service = Mock(table_id=123)
    assert (
        LocalBaserowGetRowUserServiceType().get_schema_name(mock_service)
        == "Table123Schema"
    )
    assert (
        LocalBaserowListRowsUserServiceType().get_schema_name(mock_service)
        == "Table123Schema"
    )


def test_local_baserow_table_service_type_after_update_table_change_deletes_filters_and_sorts():
    mock_instance = Mock()
    mock_from_table = Mock()
    mock_to_table = Mock()
    change_table_from_Table_to_None = {"table": (mock_from_table, None)}
    change_table_from_None_to_Table = {"table": (None, mock_to_table)}
    change_table_from_Table_to_Table = {"table": (mock_from_table, mock_to_table)}

    service_type_cls = LocalBaserowTableServiceType
    service_type_cls.model_class = Mock()
    service_type = service_type_cls()

    service_type.after_update(mock_instance, {}, change_table_from_Table_to_None)
    assert not mock_instance.service_filters.all.return_value.delete.called
    assert not mock_instance.service_sorts.all.return_value.delete.called

    service_type.after_update(mock_instance, {}, change_table_from_None_to_Table)
    assert not mock_instance.service_filters.all.return_value.delete.called
    assert not mock_instance.service_sorts.all.return_value.delete.called

    service_type.after_update(mock_instance, {}, change_table_from_Table_to_Table)
    assert mock_instance.service_filters.all.return_value.delete.called
    assert mock_instance.service_sorts.all.return_value.delete.called


@pytest.mark.django_db
def test_local_baserow_table_service_type_get_context_data(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[
            ("Ingredient", "text", {}),
        ],
    )
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="single_select",
        name="Category",
        select_options=[
            {
                "value": "Bakery",
                "color": "red",
            },
            {
                "value": "Grocery",
                "color": "green",
            },
        ],
    )

    service_type = LocalBaserowGetRowUserServiceType()
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )

    context_data = service_type.get_context_data(service)

    # The first field is a text field, so we ignore it when generating the schema
    assert "field_1" not in context_data

    # The second field should contain all the available select options
    assert context_data[f"field_{field.id}"] == list(
        field.select_options.values("id", "color", "value")
    )


@pytest.mark.django_db
def test_local_baserow_table_service_type_get_context_data_schema(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name=data_fixture.fake.name(),
        fields=[("Ingredient", "text", {})],
    )
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="single_select",
        name="Category",
        select_options=[
            {
                "value": "Bakery",
                "color": "red",
            },
            {
                "value": "Grocery",
                "color": "green",
            },
        ],
    )

    service_type = LocalBaserowGetRowUserServiceType()
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration,
        table=table,
    )

    schema = service_type.get_context_data_schema(service)

    # The first field is a text field, so we ignore it when generating the schema
    assert "field_1" not in schema["properties"]

    # The second field should have the JSON schema with the available choices
    assert schema["properties"][f"field_{field.id}"] == {
        "type": "array",
        "title": "Category",
        "default": None,
        "items": {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "id": {"type": "number"},
                "color": {"type": "string"},
            },
        },
    }
