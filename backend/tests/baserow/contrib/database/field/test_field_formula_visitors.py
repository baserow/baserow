import pytest

from baserow.contrib.database.fields.formula_visitors import (
    extract_field_id_dependencies,
    get_formula_field_error,
    replace_field_id_references,
)


def test_replace_field_id_references():
    assert (
        replace_field_id_references("get('fields.field_1')", {1: 2})
        == "get('fields.field_2')"
    )


def test_replace_field_id_references_accepts_formula_object():
    assert (
        replace_field_id_references(
            {"formula": "concat('x',get('fields.field_1'))", "mode": "simple"}, {1: 5}
        )
        == "concat('x',get('fields.field_5'))"
    )


def test_replace_field_id_references_inside_binary_ops():
    assert (
        replace_field_id_references("get('fields.field_1')+'suffix'", {1: 2})
        == "get('fields.field_2')+'suffix'"
    )
    assert (
        replace_field_id_references(
            "concat('a',get('fields.field_1')>get('fields.field_3'))", {1: 2, 3: 4}
        )
        == "concat('a',get('fields.field_2')>get('fields.field_4'))"
    )


def test_replace_field_id_references_keeps_brackets():
    assert (
        replace_field_id_references("concat('x',(get('fields.field_1')+1)*2)", {1: 9})
        == "concat('x',(get('fields.field_9')+1)*2)"
    )


def test_replace_field_id_references_skips_raw_formulas():
    assert (
        replace_field_id_references(
            {"formula": "https://example.com?x=(1", "mode": "raw"}, {1: 2}
        )
        == "https://example.com?x=(1"
    )


def test_extract_field_id_dependencies():
    assert extract_field_id_dependencies(
        "concat(get('fields.field_1'), get('fields.field_3'))"
    ) == {1, 3}
    assert extract_field_id_dependencies("") == set()


@pytest.mark.django_db
def test_get_formula_field_error(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_text_field(table=table)

    assert get_formula_field_error("", table.id) is None
    assert get_formula_field_error(f"get('fields.field_{field.id}')", table.id) is None
    assert (
        get_formula_field_error("get('fields.field_999999')", table.id)
        == "The formula references a field that no longer exists."
    )
    assert (
        get_formula_field_error("concat(broken", table.id)
        == "The formula could not be parsed."
    )
    # Raw formulas are literal text, so they are never parsed or validated.
    assert (
        get_formula_field_error(
            {"formula": "https://example.com", "mode": "raw"}, table.id
        )
        is None
    )
