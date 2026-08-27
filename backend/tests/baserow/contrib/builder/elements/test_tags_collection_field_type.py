from collections import defaultdict

import pytest

from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.pages.service import PageService
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_RAW,
    BASEROW_FORMULA_MODE_SIMPLE,
)
from baserow.core.utils import MirrorDict


@pytest.mark.django_db
def test_import_export_tags_collection_field_type(data_fixture):
    """
    Ensure that the TagsCollectionField's formulas are exported correctly
    with the updated Data Sources.
    """

    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["BMW", "#ffffff"],
        ],
    )
    name_field, color_field = fields
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table, page=page
    )
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Colors as formula",
                "type": "tags",
                "config": {
                    "values": f"get('data_source.{data_source.id}.0.{name_field.db_column}')",
                    "colors": f"get('data_source.{data_source.id}.0.{color_field.db_column}')",
                    "colors_is_formula": True,
                },
            },
            {
                "name": "Colors as hex",
                "type": "tags",
                "config": {
                    "values": "'a,b,c'",
                    "colors": "#d06060ff",
                    "colors_is_formula": False,
                },
            },
        ],
    )

    duplicated_page = PageService().duplicate_page(user, page)
    data_source2 = duplicated_page.datasource_set.first()

    id_mapping = {"builder_data_sources": {data_source.id: data_source2.id}}

    exported = table_element.get_type().export_serialized(table_element)
    imported_table_element = ElementHandler().import_element(page, exported, id_mapping)

    tags_with_formula = imported_table_element.fields.get(name="Colors as formula")
    assert tags_with_formula.config == {
        "values": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{name_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "colors": BaserowFormulaObject(
            formula=f"get('data_source.{data_source2.id}.0.{color_field.db_column}')",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "colors_is_formula": True,
        "format": "plain",
    }

    tags_without_formula = imported_table_element.fields.get(name="Colors as hex")
    assert tags_without_formula.config == {
        "values": BaserowFormulaObject(
            formula="'a,b,c'",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "colors_is_formula": False,
        "format": "plain",
        "colors": BaserowFormulaObject(
            formula="#d06060ff",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_RAW,
        ),
    }


@pytest.mark.django_db
def test_import_export_tags_collection_field_format(data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    table_element = data_fixture.create_builder_table_element(
        page=page,
        fields=[
            {
                "name": "Markdown tags",
                "type": "tags",
                "config": {
                    "values": "'**a**,b'",
                    "colors": "#d06060ff",
                    "colors_is_formula": False,
                    "format": "markdown",
                },
            },
            {
                "name": "Legacy tags",
                "type": "tags",
                # Exported before the `format` option existed.
                "config": {
                    "values": "'a,b'",
                    "colors": "#d06060ff",
                    "colors_is_formula": False,
                },
            },
        ],
    )

    exported = table_element.get_type().export_serialized(table_element)
    assert exported["fields"][0]["config"]["format"] == "markdown"
    assert "format" not in exported["fields"][1]["config"]

    id_mapping = defaultdict(lambda: MirrorDict())
    imported_table_element = ElementHandler().import_element(page, exported, id_mapping)

    markdown_tags = imported_table_element.fields.get(name="Markdown tags")
    assert markdown_tags.config["format"] == "markdown"

    legacy_tags = imported_table_element.fields.get(name="Legacy tags")
    assert legacy_tags.config["format"] == "plain"
