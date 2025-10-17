from collections import defaultdict

import pytest

from baserow.contrib.builder.elements.element_types import RepeatElementType
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import (
    ButtonElement,
    Element,
    HeadingElement,
    LinkElement,
)
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import NotificationWorkflowAction
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.utils import MirrorDict


@pytest.mark.django_db
def test_repeat_element_import_child_with_formula_with_current_record(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )

    field = fields[0]

    integration = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user
    )

    exported = {
        "id": 5,
        "name": "Page",
        "order": 8,
        "path": "/page",
        "path_params": [],
        "visibility": Page.VISIBILITY_TYPES.ALL.value,
        "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
        "roles": [],
        "elements": [
            {
                "id": 23,
                "order": "1.00000000000000000000",
                "type": "repeat",
                "parent_element_id": None,
                "place_in_container": None,
                "visibility": "all",
                "data_source_id": 3,
                "items_per_page": 20,
                "orientation": "vertical",
                "items_per_row": {"tablet": 2, "desktop": 2, "smartphone": 2},
                "roles": [],
                "role_type": Element.ROLE_TYPES.ALLOW_ALL,
            },
            {
                "id": 24,
                "order": "1.00000000000000000000",
                "type": "column",
                "parent_element_id": 23,
                "place_in_container": None,
                "visibility": "all",
                "column_amount": 3,
                "column_gap": 20,
                "alignment": "top",
                "roles": [],
                "role_type": Element.ROLE_TYPES.ALLOW_ALL,
            },
            {
                "id": 29,
                "order": "1.00000000000000000000",
                "type": "button",
                "parent_element_id": 24,
                "place_in_container": "0",
                "visibility": "all",
                "value": "get('current_record.field_424')",
                "width": "auto",
                "alignment": "left",
                "button_color": "primary",
                "roles": [],
                "role_type": Element.ROLE_TYPES.ALLOW_ALL,
            },
            {
                "id": 290,
                "order": "2.00000000000000000000",
                "type": "heading",
                "parent_element_id": 24,
                "place_in_container": "0",
                "visibility": "all",
                "value": "get('current_record.field_424')",
                "roles": [],
                "role_type": Element.ROLE_TYPES.ALLOW_ALL,
            },
            {
                "id": 291,
                "order": "3.00000000000000000000",
                "type": "link",
                "parent_element_id": 24,
                "place_in_container": "0",
                "visibility": "all",
                "value": "get('current_record.field_424')",
                "navigate_to_url": "get('current_record.field_424')",
                "page_parameters": [
                    {"name": "id", "value": "get('current_record.field_424')"}
                ],
                "query_parameters": [
                    {"name": "query_id", "value": "get('current_record.field_424')"}
                ],
                "roles": [],
                "role_type": Element.ROLE_TYPES.ALLOW_ALL,
            },
        ],
        "data_sources": [
            {
                "id": 3,
                "name": "Data source",
                "order": "1.00000000000000000000",
                "service": {
                    "id": 4,
                    "integration_id": integration.id,
                    "type": "local_baserow_list_rows",
                    "table_id": 424,
                    "view_id": None,
                    "search_query": "",
                    "filter_type": "AND",
                    "filters": [],
                    "sortings": [],
                },
            }
        ],
        "workflow_actions": [
            {
                "id": 3,
                "type": "notification",
                "order": 1,
                "page_id": 5,
                "element_id": 29,
                "event": "click",
                "title": "get('current_record.field_424')",
                "description": "",
            }
        ],
    }

    id_mapping = defaultdict(MirrorDict)
    id_mapping["database_fields"] = {424: field.id}
    id_mapping["database_tables"] = {424: table.id}

    PageHandler().import_page(builder, exported, id_mapping)

    migrated_ref = f"get('current_record.{field.db_column}')"

    button = ButtonElement.objects.all().first()
    assert button.value["formula"] == migrated_ref

    heading = HeadingElement.objects.all().first()
    assert heading.value["formula"] == migrated_ref

    action = NotificationWorkflowAction.objects.first()
    assert action.title["formula"] == migrated_ref

    link = LinkElement.objects.all().first()
    assert link.value["formula"] == migrated_ref
    assert link.navigate_to_url["formula"] == migrated_ref
    assert link.page_parameters[0]["value"]["formula"] == migrated_ref
    assert link.query_parameters[0]["value"]["formula"] == migrated_ref


@pytest.mark.django_db
def test_extract_properties_includes_schema_property_for_nested_collection(
    data_fixture,
):
    """
    Ensure the RepeatElementType::extract_properties() method includes
    the schema_property field if it exists, when the Repeat is a nested element.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)

    table = data_fixture.create_database_table(database=database)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    data_fixture.create_select_option(
        field=multiple_select_field, value="Green", color="green", order=0
    )

    page = data_fixture.create_builder_page(builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    # Create a parent Repeat element that has a data source
    parent_repeat = data_fixture.create_builder_repeat_element(
        data_source=data_source, page=page
    )

    properties = RepeatElementType().extract_properties(parent_repeat)
    assert properties == {data_source.service_id: ["id"]}

    # Create a child Repeat with a schema_property
    child_repeat = data_fixture.create_builder_repeat_element(
        page=page,
        data_source=None,
        parent_element_id=parent_repeat.id,
        schema_property=multiple_select_field.db_column,
    )
    formula_context = ElementHandler().get_import_context_addition(
        child_repeat.parent_element_id, {}
    )

    properties = RepeatElementType().extract_properties(child_repeat, **formula_context)

    # We expect that the schema_property field to be present and the ID
    assert properties == {
        data_source.service_id: [f"field_{multiple_select_field.id}", "id"]
    }


@pytest.mark.django_db
def test_extract_properties_includes_schema_property_for_single_row(
    data_fixture,
):
    """
    Ensure the RepeatElementType::extract_properties() method includes
    the schema_property field if it exists, when the repeat uses a Get Row service.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )

    table = data_fixture.create_database_table(database=database)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option = data_fixture.create_select_option(
        field=multiple_select_field, value="Green", color="green", order=0
    )

    handler = RowHandler()
    handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{multiple_select_field.id}": [option.id],
            },
        ],
    )

    page = data_fixture.create_builder_page(builder=builder)
    get_row_service = data_fixture.create_local_baserow_get_row_service(
        integration=integration,
        row_id=table.get_model().objects.first().id,
    )
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        table=table,
        service=get_row_service,
    )

    # Create a Repeat element that uses the Single Row data source
    repeat = data_fixture.create_builder_repeat_element(
        data_source=data_source,
        page=page,
        schema_property=multiple_select_field.db_column,
    )

    properties = RepeatElementType().extract_properties(repeat)
    assert properties == {
        data_source.service_id: [f"field_{multiple_select_field.id}", "id"]
    }
