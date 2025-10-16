"""
Test the LinkCollectionFieldType class.
"""

import pytest

from baserow.contrib.builder.elements.collection_field_types import (
    LinkCollectionFieldType,
)
from baserow.contrib.builder.elements.models import LinkElement
from baserow.contrib.builder.elements.receivers import (
    page_deleted_update_link_collection_fields,
)
from baserow.contrib.builder.elements.registries import collection_field_type_registry
from baserow.contrib.builder.pages.service import PageService
from baserow.contrib.builder.pages.signals import page_deleted
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE


def test_registering_link_collection_field_type_connects_to_page_deleted_signal():
    try:
        collection_field_type_registry.get(LinkCollectionFieldType.type)
    except InstanceTypeDoesNotExist:
        collection_field_type_registry.register(LinkCollectionFieldType.type)
    registered_handlers = [receiver[1]() for receiver in page_deleted.receivers]
    assert page_deleted_update_link_collection_fields in registered_handlers


def test_unregistering_link_collection_field_type_disconnects_from_page_deleted_signal():
    collection_field_type_registry.unregister(LinkCollectionFieldType.type)
    registered_handlers = [receiver[1]() for receiver in page_deleted.receivers]
    assert page_deleted_update_link_collection_fields not in registered_handlers


@pytest.mark.django_db
def test_import_export_link_collection_field_type(data_fixture):
    """
    Ensure that the LinkCollectionField's formulas are exported correctly
    with the updated Data Sources.
    """

    user, _ = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["Foo"],
        ],
    )
    text_field = fields[0]
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Foo Link Field",
                "type": "link",
                "config": {
                    "link_name": f"get('data_source.{data_source.id}.0.{text_field.db_column}')",
                    "navigate_to_url": f"get('data_source.{data_source.id}.0.{text_field.db_column}')",
                    "navigation_type": "page",
                    "navigate_to_page_id": None,
                    "page_parameters": [
                        {
                            "name": "fooPageParam",
                            "value": f"get('data_source.{data_source.id}.field_1')",
                        },
                    ],
                    "query_parameters": [
                        {
                            "name": "fooQueryParam",
                            "value": f"get('data_source.{data_source.id}.field_1')",
                        },
                    ],
                    "target": "self",
                    "variant": LinkElement.VARIANTS.LINK,
                },
            },
        ],
    )

    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()

    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}

    exported = table_element.get_type().export_serialized(table_element)

    # Here we omit the "variant" property in order to test the default attribution,
    # i.e, if none is provided it should use the default value provided in the
    # `serializer_field_overrides`
    exported["fields"][0]["config"].pop("variant")

    imported_table_element = table_element.get_type().import_serialized(
        page, exported, id_mapping
    )

    imported_field = imported_table_element.fields.get(name="Foo Link Field")
    assert imported_field.config == {
        "link_name": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{text_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "navigate_to_url": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{text_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "navigate_to_page_id": None,
        "navigation_type": "page",
        "query_parameters": [
            {
                "name": "fooQueryParam",
                "value": BaserowFormulaObject(
                    formula=f"get('data_source.{data_source2.id}.field_1')",
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                ),
            },
        ],
        "page_parameters": [
            {
                "name": "fooPageParam",
                "value": BaserowFormulaObject(
                    formula=f"get('data_source.{data_source2.id}.field_1')",
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                ),
            },
        ],
        "target": "self",
        "variant": LinkElement.VARIANTS.LINK,
    }
