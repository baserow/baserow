"""
Whether a formula can be stored is decided from the formula and what the page has,
without evaluating it.
"""

import pytest

from baserow.core.graph.types import GraphPointPosition
from baserow.core.tools.errors import ToolInputError
from baserow_enterprise.builder.tools import data_sources
from baserow_enterprise.builder.tools.formulas import (
    current_record_of,
    formula_problem,
    page_formula_context,
)
from baserow_enterprise.builder.tools.types import DataSourceChanges


@pytest.fixture
def site(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
        query_params=[{"name": "q", "type": "text"}],
    )
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=builder_ctx["workspace"]
        )
    )
    fields = {
        "text": data_fixture.create_text_field(table=table, primary=True, name="Name"),
        "number": data_fixture.create_number_field(table=table),
        "date": data_fixture.create_date_field(table=table),
        "duration": data_fixture.create_duration_field(table=table),
        "select": data_fixture.create_multiple_select_field(table=table),
    }
    rows = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, name="Rows"
    )
    row = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, table=table, row_id="'1'", name="Row"
    )
    form_field = data_fixture.create_builder_input_text_element(page=page)
    return {
        **builder_ctx,
        "page": page,
        "fields": fields,
        "rows": rows,
        "row": row,
        "form_field": form_field,
    }


def problem(site, formula, **kwargs):
    return formula_problem(
        "value", formula, page_formula_context(site["page"]), **kwargs
    )


def row_path(site, field):
    return f"data_source.{site['rows'].id}.0.field_{site['fields'][field].id}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "template",
    [
        "day(get('{date}'))",
        "datetime_format(get('{date}'), 'YYYY')",
        "greater_than(get('{number}'), 1)",
        "greater_than(get('{duration}'), 1)",
        "add(get('{text}'), 1)",
    ],
)
def test_functions_get_any_type_of_field(site, template):
    formula = template.format(
        date=row_path(site, "date"),
        number=row_path(site, "number"),
        duration=row_path(site, "duration"),
        text=row_path(site, "text"),
    )

    assert problem(site, formula) is None


@pytest.mark.django_db
def test_paths_the_page_has_are_accepted(site):
    rows, row = site["rows"].id, site["row"].id
    select = site["fields"]["select"].id
    for formula in [
        "add(get('page_parameter.id'), 1)",
        "get('page_parameter.q')",
        "get('user.first_name')",
        "get('user.email')",
        f"get('form_data.{site['form_field'].id}')",
        f"get('data_source.{rows}')",
        f"get('data_source.{rows}.0')",
        f"get('data_source.{rows}.5.id')",
        f"get('data_source.{rows}.*.field_{site['fields']['text'].id}')",
        f"get('data_source.{rows}.0.Name')",
        f"get('data_source.{rows}.0.field_{select}.0.value')",
        f"get('data_source.{rows}.0.field_{select}.*.value')",
        f"get('data_source.{row}.field_{site['fields']['text'].id}')",
        f"get('data_source_context.{rows}.total_count')",
        "concat('a', get('user.id'), 'b')",
        "now()",
        "'just text'",
    ]:
        assert problem(site, formula) is None, formula


@pytest.mark.django_db
def test_a_data_source_of_the_shared_page_is_accepted(data_fixture, site):
    shared = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=site["builder"].shared_page, name="Shared"
    )

    assert problem(site, f"get('data_source.{shared.id}.0.id')") is None


@pytest.mark.django_db
def test_a_data_source_without_a_table_reads_anything(data_fixture, site):
    empty = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=site["page"], table=None, name="Empty"
    )

    assert problem(site, f"get('data_source.{empty.id}.0.field_1')") is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,expected",
    [
        ("get('page_parameter.id'", "needs a formula"),
        ("the id of the page", "needs a formula"),
        ("   ", "needs a formula"),
        ("no_such_function(1)", "no_such_function"),
        ("upper('a', 'b')", "upper"),
        ("get('')", "not a valid formula"),
        ("add('abc', 1)", "not a valid formula"),
        ("get('nowhere.id')", "nowhere"),
        ("get('page_parameter.missing')", "missing"),
        ("get('page_parameter')", "page_parameter"),
        ("get('form_data.999999')", "999999"),
        ("get('data_source.999999.0.id')", "999999"),
        ("get('data_source.rows')", "rows"),
        ("get('current_record.id')", "current_record"),
        ("get('previous_action.5.id')", "previous_action"),
        ("to_duration(99999999999999999999)", "not a valid formula"),
        ("duration_format(99999999999999999999,'a')", "not a valid formula"),
        ("get('[')", "doesn't name anything"),
    ],
)
def test_refused_with_a_useful_message(site, formula, expected):
    assert expected in problem(site, formula)


@pytest.mark.django_db
def test_a_field_the_data_source_does_not_have_names_its_fields(site):
    rows = site["rows"].id

    message = problem(site, f"get('data_source.{rows}.0.field_999999')")

    assert "field_999999" in message
    assert f"field_{site['fields']['text'].id} (Name)" in message


@pytest.mark.django_db
def test_a_row_of_a_list_data_source_needs_an_index(site):
    field = site["fields"]["text"].id

    assert problem(site, f"get('data_source.{site['rows'].id}.field_{field}')")


@pytest.mark.django_db
def test_a_path_below_a_plain_value_is_refused(site):
    assert problem(site, f"get('{row_path(site, 'text')}.deeper')")


@pytest.mark.django_db
def test_a_data_source_on_another_page_is_refused(data_fixture, site):
    other = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=data_fixture.create_builder_page(builder=site["builder"]), name="Other"
    )

    message = problem(site, f"get('data_source.{other.id}.0.id')")

    assert str(other.id) in message
    assert f"{site['rows'].id} (Rows)" in message


@pytest.mark.django_db
def test_previous_action_can_be_allowed(site):
    assert problem(site, "get('previous_action.5.id')", allow_previous_action=True) is (
        None
    )


@pytest.mark.django_db
def test_every_path_of_a_formula_is_checked(site):
    assert "missing" in problem(
        site, "concat(get('user.id'), upper(get('page_parameter.missing')))"
    )


@pytest.mark.django_db
def test_current_record_is_accepted_inside_a_collection(data_fixture, site):
    repeat = data_fixture.create_builder_repeat_element(
        page=site["page"], data_source=site["rows"]
    )
    heading = data_fixture.create_builder_heading_element(
        page=site["page"],
        value="''",
        reference_element=repeat,
        position=GraphPointPosition.CHILD,
    )
    context = page_formula_context(site["page"])

    with current_record_of(context, "element", heading):
        accepted = formula_problem("value", "get('current_record.__idx__')", context)

    assert accepted is None


@pytest.mark.django_db
@pytest.mark.parametrize("row_id", ["", "   "])
def test_update_refuses_a_blank_row_id_on_a_get_row(site, row_id):
    with pytest.raises(ToolInputError, match="row_id"):
        data_sources.update_data_source(
            site["ctx"], site["row"].id, DataSourceChanges(row_id=row_id)
        )

    service = site["row"].service.specific
    service.refresh_from_db()
    assert service.row_id["formula"] == "'1'"


@pytest.mark.django_db
def test_update_leaves_row_id_alone_when_it_is_not_given(site):
    result = data_sources.update_data_source(
        site["ctx"], site["row"].id, DataSourceChanges(name="Renamed")
    )

    assert result["updated_data_source"]["name"] == "Renamed"
    service = site["row"].service.specific
    service.refresh_from_db()
    assert service.row_id["formula"] == "'1'"


@pytest.mark.django_db
def test_deeply_nested_gets_are_checked_in_linear_time(site, monkeypatch):
    from baserow_enterprise.builder.tools import formulas

    calls = 0
    original = formulas._GetPathsVisitor.visitFunctionCall

    def counting(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(formulas._GetPathsVisitor, "visitFunctionCall", counting)
    depth = 200
    formula = "get(" * depth + "'page_parameter.id'" + ")" * depth

    assert problem(site, formula) is None
    assert calls == depth


@pytest.mark.django_db
def test_a_data_source_context_must_be_on_the_page(data_fixture, site):
    other = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=data_fixture.create_builder_page(), name="Other"
    )
    rows = site["rows"].id

    assert problem(site, f"get('data_source_context.{rows}.total_count')") is None
    refused = problem(site, f"get('data_source_context.{other.id}.total_count')")
    assert refused and "isn't on this page" in refused
    assert "isn't on this page" in problem(site, "get('data_source_context.x')")
