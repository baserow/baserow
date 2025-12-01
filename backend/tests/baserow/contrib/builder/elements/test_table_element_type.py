import json
import uuid
from collections import defaultdict

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import (
    CollectionField,
    Element,
    LinkElement,
    TableElement,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.workflow_actions.models import NotificationWorkflowAction
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.utils import MirrorDict


@pytest.mark.django_db
def test_create_table_element_without_fields(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    ElementService().create_element(
        user,
        element_type_registry.get("table"),
        page=page,
        data_source_id=data_source1.id,
    )

    created_element = Element.objects.last().specific

    assert created_element.data_source.id == data_source1.id


@pytest.mark.django_db
def test_create_table_element_with_fields(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    ElementService().create_element(
        user,
        element_type_registry.get("table"),
        page=page,
        data_source_id=data_source1.id,
        fields=[
            {"name": "Field 1", "type": "text", "config": {"value": "get('test1')"}},
            {"name": "Field 2", "type": "text", "config": {"value": "get('test1')"}},
        ],
    )

    created_element = Element.objects.last().specific

    assert created_element.data_source.id == data_source1.id

    fields = list(created_element.fields.all())

    assert len(fields) == 2

    fields[0].name == "Field 1"
    fields[1].name == "Field 2"


@pytest.mark.django_db
def test_update_table_element_without_fields(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    table_element = data_fixture.create_builder_table_element(page=page)

    ElementService().update_element(
        user,
        table_element,
        data_source_id=data_source1.id,
    )

    table_element.refresh_from_db()

    assert table_element.data_source.id == data_source1.id

    fields = list(table_element.fields.all())

    assert len(fields) == 3

    fields[0].name == "Field 1"
    fields[1].name == "Field 2"
    fields[2].name == "Field 3"


@pytest.mark.django_db
def test_update_table_element_with_fields(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table_element = data_fixture.create_builder_table_element(page=page)
    uuids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]

    ElementService().update_element(
        user,
        table_element,
        fields=[
            {
                "name": "New field 1",
                "type": "text",
                "config": {"value": "get('test1')"},
                "uid": uuids[0],
            },
            {
                "name": "New field 2",
                "type": "text",
                "config": {"value": "get('test2')"},
                "uid": uuids[1],
            },
        ],
    )

    table_element.refresh_from_db()

    fields = list(CollectionField.objects.all())

    assert len(fields) == 2

    fields[0].name == "New field 1"
    fields[1].name == "New field 2"

    ElementService().update_element(
        user,
        table_element,
        fields=[
            {
                "name": "New field 3",
                "type": "text",
                "config": {"value": "get('test3')"},
                "uid": uuids[0],
            },
            {
                "name": "New field 4",
                "type": "text",
                "config": {"value": "get('test4')"},
                "uid": uuids[1],
            },
        ],
    )

    fields = list(CollectionField.objects.all())

    # Check that we keep the same field count in db after a second update
    assert len(fields) == 2


@pytest.mark.django_db
def test_delete_table_element_remove_fields(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    table_element = data_fixture.create_builder_table_element(page=page)

    assert CollectionField.objects.count() == 3

    ElementService().delete_element(user, table_element)

    assert CollectionField.objects.count() == 0


@pytest.mark.django_db
def test_duplicate_table_element_with_current_record_formulas(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )

    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )

    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source1,
        fields=[
            {
                "name": "Field 1",
                "type": "text",
                "config": {"value": f"get('current_record.field_{fields[0].id}')"},
            },
            {
                "name": "Field 2",
                "type": "link",
                "config": {
                    "page_parameters": [],
                    "query_parameters": [],
                    "navigate_to_page_id": None,
                    "navigation_type": "custom",
                    "navigate_to_url": f"get('current_record.field_{fields[0].id}')",
                    "link_name": f"get('current_record.field_{fields[0].id}')",
                    "target": "self",
                    "variant": LinkElement.VARIANTS.BUTTON,
                },
            },
        ],
    )

    result = ElementHandler().duplicate_element(table_element)

    assert [f.config for f in result["elements"][0].fields.all()] == [
        {
            "value": BaserowFormulaObject(
                formula=f"get('current_record.field_{fields[0].id}')",
                version=BASEROW_FORMULA_VERSION_INITIAL,
                mode=BASEROW_FORMULA_MODE_SIMPLE,
            )
        },
        {
            "page_parameters": [],
            "query_parameters": [],
            "navigate_to_page_id": None,
            "navigation_type": "custom",
            "navigate_to_url": BaserowFormulaObject(
                formula=f"get('current_record.field_{fields[0].id}')",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "link_name": BaserowFormulaObject(
                formula=f"get('current_record.field_{fields[0].id}')",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "target": "self",
            "variant": LinkElement.VARIANTS.BUTTON,
        },
    ]


@pytest.mark.django_db
def test_import_table_element_with_current_record_formulas_with_update(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )

    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    uuids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]

    IMPORT_REF = {
        "id": 42,
        "order": "1.00000000000000000000",
        "type": "table",
        "parent_element_id": None,
        "place_in_container": None,
        "style_padding_top": 10,
        "style_padding_bottom": 10,
        "data_source_id": 42,
        "items_per_page": 20,
        "roles": [],
        "role_type": Element.ROLE_TYPES.ALLOW_ALL,
        "fields": [
            {
                "name": "Field 1",
                "config": {
                    "value": BaserowFormulaObject(
                        formula="get('current_record.field_42')",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    )
                },
                "type": "text",
                "uid": uuids[0],
            },
            {
                "name": "Field 2",
                "config": {
                    "page_parameters": [],
                    "query_parameters": [],
                    "navigate_to_page_id": None,
                    "navigation_type": "custom",
                    "navigate_to_url": BaserowFormulaObject(
                        formula="get('current_record.field_42')",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    ),
                    "link_name": BaserowFormulaObject(
                        formula="get('current_record.field_42')",
                        mode=BASEROW_FORMULA_MODE_SIMPLE,
                        version=BASEROW_FORMULA_VERSION_INITIAL,
                    ),
                    "target": "self",
                    "variant": LinkElement.VARIANTS.BUTTON,
                },
                "type": "link",
                "uid": uuids[1],
            },
        ],
    }

    id_mapping = {
        "database_fields": {42: fields[0].id},
        "builder_data_sources": {42: data_source1.id},
    }

    ElementHandler().import_element(page, IMPORT_REF, id_mapping)

    [imported_table_element] = page.element_set.all()

    assert imported_table_element.specific.data_source_id == data_source1.id

    assert [f.config for f in imported_table_element.specific.fields.all()] == [
        {
            "value": BaserowFormulaObject(
                formula=f"get('current_record.field_{fields[0].id}')",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            )
        },
        {
            "page_parameters": [],
            "query_parameters": [],
            "navigate_to_page_id": None,
            "navigation_type": "custom",
            "navigate_to_url": BaserowFormulaObject(
                formula=f"get('current_record.field_{fields[0].id}')",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "link_name": BaserowFormulaObject(
                formula=f"get('current_record.field_{fields[0].id}')",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            ),
            "target": "self",
            "variant": LinkElement.VARIANTS.BUTTON,
        },
    ]


@pytest.mark.django_db
def test_delete_table_element_removes_associated_workflow_actions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source1,
        fields=[
            {
                "name": "Field",
                "type": "button",
                "config": {"label": "Click me"},
            },
        ],
    )
    data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=page,
        element=table_element,
        event=f"{table_element.fields.first().uid}_click",
    )

    assert NotificationWorkflowAction.objects.count() == 1
    ElementService().delete_element(user, table_element)
    assert NotificationWorkflowAction.objects.count() == 0


@pytest.mark.django_db
def test_delete_table_field_removes_associated_workflow_actions(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source1,
        fields=[
            {
                "name": "Field",
                "type": "button",
                "config": {"label": "Click me"},
            },
        ],
    )
    workflow_action = data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=page,
        element=table_element,
        event=f"{table_element.fields.first().uid}_click",
    )

    assert NotificationWorkflowAction.objects.count() == 1
    ElementService().update_element(user, table_element, fields=[])
    assert NotificationWorkflowAction.objects.count() == 0


@pytest.mark.django_db
def test_table_element_import_export(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source1 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source1,
        fields=[
            {
                "name": "Field",
                "type": "button",
                "config": {"label": "'Click me'"},
            },
        ],
    )
    table_element_type = table_element.get_type()

    # Export the table element and check there are no table elements after deleting it
    exported = table_element_type.export_serialized(table_element)
    ElementService().delete_element(user, table_element)
    assert json.dumps(exported)
    assert TableElement.objects.count() == 0

    # After importing the table element the fields should be properly imported too
    id_mapping = defaultdict(lambda: MirrorDict())
    table_element_type.import_serialized(page, exported, id_mapping)
    assert (
        TableElement.objects.filter(
            page=page,
            data_source=data_source1,
            fields__name="Field",
            fields__type="button",
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_table_element_import_fields_with_no_uid(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    exported = {
        "id": 1,
        "order": "1.00000000000000000000",
        "type": "table",
        "parent_element_id": None,
        "roles": [],
        "role_type": Element.ROLE_TYPES.ALLOW_ALL,
        "fields": [
            {
                # NOTE: 'uid' property is missing here
                "name": "Field",
                "type": "button",
                "config": {"label": "'Click me'"},
            }
        ],
        "data_source_id": data_source.id,
    }
    table_element_type = data_fixture.create_builder_table_element().get_type()
    id_mapping = defaultdict(lambda: MirrorDict())

    table_element = table_element_type.import_serialized(page, exported, id_mapping)
    assert table_element.fields.first().uid is not None


@pytest.mark.django_db
def test_table_element_import_field_with_formula_with_current_record(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table
    )

    exported = {
        "id": 1,
        "order": "1.00000000000000000000",
        "type": "table",
        "parent_element_id": None,
        "roles": [],
        "role_type": Element.ROLE_TYPES.ALLOW_ALL,
        "fields": [
            {
                "uid": "7778cf93-77e5-4064-ab32-3342e2b1656a",
                "name": "Field",
                "type": "button",
                "config": {"label": "get('current_record.field_424')"},
            }
        ],
        "data_source_id": 42,
    }
    table_element_type = data_fixture.create_builder_table_element().get_type()

    id_mapping = defaultdict(MirrorDict)
    id_mapping["builder_data_sources"] = {42: data_source.id}
    id_mapping["database_fields"] = {424: fields[0].id}

    table_element = table_element_type.import_serialized(page, exported, id_mapping)
    assert (
        table_element.fields.first().config["label"]["formula"]
        == f"get('current_record.field_{fields[0].id}')"
    )


@pytest.mark.django_db
def test_import_context_addition_returns_data_source_id(data_fixture):
    """
    Test the TableElementType::import_context_addition() method.

    Ensure the data_source_id is included in the returned dict.
    """

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source()
    table_element = data_fixture.create_builder_table_element(
        data_source=data_source,
    )
    table_element_type = table_element.get_type()

    context = table_element_type.import_context_addition(table_element)

    assert context["data_source_id"] == data_source.id


@pytest.mark.django_db
def test_table_element_duplication_regenerates_collection_field_uids(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source()
    source_table_element = data_fixture.create_builder_table_element(
        data_source=data_source,
        fields=[
            {
                "name": "FieldA",
                "type": "button",
                "config": {"value": f"'Click me')"},
            },
        ],
    )
    source_collection_field = source_table_element.fields.get(name="FieldA")
    source_workflow_action = data_fixture.create_workflow_action(
        NotificationWorkflowAction,
        page=source_table_element.page,
        element=source_table_element,
        event=f"{source_collection_field.uid}_click",
    )

    elements_and_workflow_actions_duplicated = ElementHandler().duplicate_element(
        source_table_element
    )
    duplicated_table_element = elements_and_workflow_actions_duplicated["elements"][0]
    duplicated_collection_field = duplicated_table_element.fields.get(name="FieldA")
    duplicated_workflow_action = elements_and_workflow_actions_duplicated[
        "workflow_actions"
    ][0]

    assert source_collection_field.uid != duplicated_collection_field.uid
    assert source_workflow_action.event != duplicated_workflow_action.event
    assert (
        duplicated_workflow_action.event == f"{duplicated_collection_field.uid}_click"
    )
