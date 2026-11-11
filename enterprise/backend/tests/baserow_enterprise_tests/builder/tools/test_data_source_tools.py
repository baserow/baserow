"""
The shared data source tools store the formulas they are given and report the rest,
without a model. The conftest of this folder fails any model call.
"""

import pytest

from baserow.contrib.builder.data_sources.exceptions import DataSourceDoesNotExist
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.core.formula.literals import wrap_static_string
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.tools.errors import ToolInputError, tool_error_message
from baserow_enterprise.builder.tools import (
    BuilderWriteOptions,
    data_sources,
    formulas,
)
from baserow_enterprise.builder.tools.types import DataSourceChanges, DataSourceCreate


@pytest.fixture
def site(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Item",
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    table = builder_ctx["data_source"].service.specific.table
    return {**builder_ctx, "page": page, "table": table}


def service_of(data_source_id):
    return DataSource.objects.get(id=data_source_id).service.specific


@pytest.mark.django_db
def test_create_stores_explicit_formulas_and_reports_descriptions(site):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="explicit",
                name="Explicit",
                type="list_rows",
                table_id=site["table"].id,
                search_query="get('page_parameter.id')",
            ),
            DataSourceCreate(
                ref="described",
                name="Described",
                type="list_rows",
                table_id=site["table"].id,
                search_query="$formula: the text of the search box",
            ),
        ],
    )

    ids = result["ref_to_id_map"]
    assert [ds["ref"] for ds in result["created_data_sources"]] == [
        "explicit",
        "described",
    ]
    explicit = service_of(ids["explicit"]).search_query
    assert explicit["formula"] == "get('page_parameter.id')"
    assert explicit["mode"] == BASEROW_FORMULA_MODE_ADVANCED

    assert service_of(ids["described"]).search_query["formula"] == "''"
    assert len(result["formula_errors"]) == 1
    entry = result["formula_errors"][0]
    assert set(entry) == {"data_source_id", "field", "formula", "error"}
    assert entry["data_source_id"] == ids["described"]
    assert entry["field"] == "search_query"
    assert entry["formula"] == "$formula: the text of the search box"
    assert "errors" not in result


@pytest.mark.django_db
def test_create_reports_a_formula_that_does_not_resolve_on_the_page(site):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="ds",
                name="Search",
                type="list_rows",
                table_id=site["table"].id,
                search_query="get('page_parameter.missing')",
            )
        ],
    )

    data_source_id = result["ref_to_id_map"]["ds"]
    assert service_of(data_source_id).search_query["formula"] == "''"
    assert result["formula_errors"][0]["data_source_id"] == data_source_id
    assert "missing" in result["formula_errors"][0]["error"]


SEARCH_QUERIES = [
    ("upper('abc')", "upper('abc')"),
    ("red shoes", "'red shoes'"),
    ("nosuch('x')", wrap_static_string("nosuch('x')")),
    ("Hello (world)", "'Hello (world)'"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("given, stored", SEARCH_QUERIES)
def test_create_treats_a_search_query_like_element_text(site, given, stored):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="ds",
                name="Search",
                type="list_rows",
                table_id=site["table"].id,
                search_query=given,
            )
        ],
    )

    assert "formula_errors" not in result
    data_source_id = result["ref_to_id_map"]["ds"]
    assert service_of(data_source_id).search_query["formula"] == stored


@pytest.mark.django_db
@pytest.mark.parametrize("given, stored", SEARCH_QUERIES)
def test_update_treats_a_search_query_like_element_text(site, given, stored):
    created = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="ds", name="Search", type="list_rows", table_id=site["table"].id
            )
        ],
    )
    data_source_id = created["ref_to_id_map"]["ds"]

    result = data_sources.update_data_source(
        site["ctx"], data_source_id, DataSourceChanges(search_query=given)
    )

    assert "formula_errors" not in result
    assert service_of(data_source_id).search_query["formula"] == stored


@pytest.mark.django_db
def test_create_makes_a_list_rows_on_a_table_that_already_has_one(site):
    first = {"name": "First", "type": "list_rows", "table_id": site["table"].id}
    data_sources.create_data_sources(
        site["ctx"], site["page"].id, [DataSourceCreate(ref="a", **first)]
    )

    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="b", name="Second", type="list_rows", table_id=site["table"].id
            )
        ],
    )

    assert [ds["ref"] for ds in result["created_data_sources"]] == ["b"]
    assert DataSource.objects.filter(page=site["page"]).count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "row_id",
    [
        "$formula: the id page parameter",
        "get('page_parameter.missing')",
        "the current product",
    ],
)
def test_get_row_with_a_row_id_that_is_not_a_formula_is_not_created(site, row_id):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=site["table"].id,
                row_id=row_id,
            ),
            DataSourceCreate(
                ref="other", name="Other", type="list_rows", table_id=site["table"].id
            ),
        ],
    )

    assert not DataSource.objects.filter(page=site["page"], name="Row").exists()
    assert [ds["ref"] for ds in result["created_data_sources"]] == ["other"]
    assert len(result["errors"]) == 1
    assert result["errors"][0].startswith("row: ")
    assert "row_id" in result["errors"][0]
    assert "formula_errors" not in result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "row_id", ["get('page_parameter.id')", "add(get('page_parameter.id'), 1)"]
)
def test_get_row_with_an_explicit_row_id_is_created_and_stored(site, row_id):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=site["table"].id,
                row_id=row_id,
            )
        ],
    )

    stored = service_of(result["ref_to_id_map"]["row"]).row_id
    assert stored["formula"] == row_id
    assert stored["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert "errors" not in result
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_defer_creates_the_get_row_with_the_placeholder_and_reports_the_value(site):
    result = data_sources.create_data_sources_with_options(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=site["table"].id,
                row_id="$formula: the id page parameter",
            )
        ],
        BuilderWriteOptions(defer_required_formulas=True),
    )

    data_source_id = result["ref_to_id_map"]["row"]
    assert service_of(data_source_id).row_id["formula"] == "''"
    assert result["formula_errors"] == [
        {
            "data_source_id": data_source_id,
            "field": "row_id",
            "formula": "$formula: the id page parameter",
            "error": result["formula_errors"][0]["error"],
        }
    ]


@pytest.mark.django_db
def test_create_keeps_the_items_around_a_bad_one(site):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="a", name="A", type="list_rows", table_id=site["table"].id
            ),
            DataSourceCreate(ref="bad", name="Bad", type="list_rows", table_id=999999),
            DataSourceCreate(
                ref="c", name="C", type="list_rows", table_id=site["table"].id
            ),
        ],
    )

    assert [ds["ref"] for ds in result["created_data_sources"]] == ["a", "c"]
    assert result["errors"] == ["bad: Table with id 999999 not found."]


@pytest.mark.django_db
def test_create_on_a_page_of_another_workspace_is_not_found(data_fixture, site):
    other_page = data_fixture.create_builder_page(user=site["user"])

    with pytest.raises(PageDoesNotExist) as exc:
        data_sources.create_data_sources(
            site["ctx"],
            other_page.id,
            [
                DataSourceCreate(
                    ref="a", name="A", type="list_rows", table_id=site["table"].id
                )
            ],
        )
    assert tool_error_message(exc.value) == "Not found in this workspace."


@pytest.mark.django_db
def test_update_stores_an_explicit_formula(data_fixture, site):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'", name="Before"
    )

    result = data_sources.update_data_source(
        site["ctx"],
        data_source.id,
        DataSourceChanges(name="After", row_id="get('page_parameter.id')"),
    )

    assert result["updated_data_source"]["id"] == data_source.id
    assert result["updated_data_source"]["name"] == "After"
    assert "formula_errors" not in result
    row_id = service_of(data_source.id).row_id
    assert row_id["formula"] == "get('page_parameter.id')"
    assert row_id["mode"] == BASEROW_FORMULA_MODE_ADVANCED


@pytest.mark.django_db
def test_get_row_takes_a_number_as_its_row_id(site):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=site["table"].id,
                row_id="7",
            )
        ],
    )

    assert not result.get("errors")
    assert service_of(result["ref_to_id_map"]["row"]).row_id["formula"] == "'7'"


@pytest.mark.django_db
def test_update_with_plain_text_keeps_the_row_id_and_reports_it(data_fixture, site):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )

    result = data_sources.update_data_source(
        site["ctx"],
        data_source.id,
        DataSourceChanges(row_id="the current product"),
    )

    assert service_of(data_source.id).row_id["formula"] == "'1'"
    assert result["formula_errors"][0]["field"] == "row_id"


@pytest.mark.django_db
def test_update_takes_a_number_as_the_row_id(data_fixture, site):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )

    result = data_sources.update_data_source(
        site["ctx"], data_source.id, DataSourceChanges(row_id="7")
    )

    assert "formula_errors" not in result
    assert service_of(data_source.id).row_id["formula"] == "'7'"


@pytest.mark.django_db
def test_update_with_a_description_keeps_the_value_and_reports_it(data_fixture, site):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=site["page"], table=site["table"], row_id="'1'"
    )

    result = data_sources.update_data_source(
        site["ctx"],
        data_source.id,
        DataSourceChanges(row_id="$formula: the id page parameter"),
    )

    assert service_of(data_source.id).row_id["formula"] == "'1'"
    entry = result["formula_errors"][0]
    assert entry["data_source_id"] == data_source.id
    assert entry["field"] == "row_id"


@pytest.mark.django_db
def test_update_of_a_data_source_of_another_workspace_is_not_found(data_fixture, site):
    other_page = data_fixture.create_builder_page(user=site["user"])
    other = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=other_page, user=site["user"]
    )

    with pytest.raises(DataSourceDoesNotExist) as exc:
        data_sources.update_data_source(
            site["ctx"], other.id, DataSourceChanges(name="Stolen")
        )
    assert tool_error_message(exc.value) == "Not found in this workspace."


@pytest.mark.django_db
@pytest.mark.parametrize("row_id", [None, "", "   "])
def test_get_row_without_a_row_id_reads_the_first_row(site, row_id):
    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=site["table"].id,
                row_id=row_id,
            )
        ],
    )

    assert "errors" not in result
    data_source = DataSource.objects.get(id=result["ref_to_id_map"]["row"])
    assert data_source.service.specific.row_id["formula"] == ""


@pytest.mark.django_db
def test_update_with_a_blank_row_id_removes_the_row_id(site):
    created = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="row",
                name="Row",
                type="get_row",
                table_id=site["table"].id,
                row_id="2",
            )
        ],
    )
    data_source_id = created["ref_to_id_map"]["row"]

    data_sources.update_data_source(
        site["ctx"], data_source_id, DataSourceChanges(row_id="")
    )

    data_source = DataSource.objects.get(id=data_source_id)
    assert data_source.service.specific.row_id["formula"] == ""


@pytest.mark.django_db
def test_an_error_after_the_batch_committed_still_reports_what_was_created(
    site, monkeypatch
):
    def broken(page):
        raise RuntimeError("broken")

    monkeypatch.setattr(formulas, "page_formula_context", broken)

    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="ds",
                name="Search",
                type="list_rows",
                table_id=site["table"].id,
                search_query="get('page_parameter.id')",
            )
        ],
    )

    assert [ds["ref"] for ds in result["created_data_sources"]] == ["ds"]
    assert result["formula_errors"][0]["error"] == "Internal error."


@pytest.mark.django_db
def test_a_bad_sort_field_names_no_tool(site, data_fixture):
    other_field = data_fixture.create_text_field()

    result = data_sources.create_data_sources(
        site["ctx"],
        site["page"].id,
        [
            DataSourceCreate(
                ref="ds",
                name="Sorted",
                type="list_rows",
                table_id=site["table"].id,
                sortings=[{"field_id": other_field.id}],
            )
        ],
    )

    assert result["errors"][0].startswith("ds: ")
    assert "get_table" not in result["errors"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("row_id", ["5", "get('page_parameter.id')"])
def test_update_refuses_a_row_id_on_a_data_source_that_reads_many_rows(
    builder_ctx, row_id
):
    with pytest.raises(ToolInputError, match="row_id"):
        data_sources.update_data_source(
            builder_ctx["ctx"],
            builder_ctx["data_source"].id,
            DataSourceChanges(name="Renamed", row_id=row_id),
        )

    assert DataSource.objects.get(id=builder_ctx["data_source"].id).name == "Products"


@pytest.mark.django_db
def test_update_stores_a_search_query_on_a_get_row(data_fixture, builder_ctx):
    get_row = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=builder_ctx["page"],
        table=builder_ctx["data_source"].service.specific.table,
    )

    data_sources.update_data_source(
        builder_ctx["ctx"], get_row.id, DataSourceChanges(search_query="abc")
    )

    assert service_of(get_row.id).search_query["formula"] == "'abc'"
