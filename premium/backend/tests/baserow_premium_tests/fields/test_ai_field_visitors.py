import pytest

from baserow.core.formula import BaserowFormulaSyntaxError
from baserow_premium.fields.visitors import (
    get_ai_prompt_error,
    replace_field_id_references,
)


@pytest.mark.field_ai
def test_replace_field_id_references():
    assert (
        replace_field_id_references("get('fields.field_1')", {1: 2})
        == "get('fields.field_2')"
    )


@pytest.mark.field_ai
def test_replace_multiple_field_id_references():
    assert (
        replace_field_id_references(
            "concat(get('fields.field_1'),get('fields.field_12'))", {1: 2, 3: 4, 12: 13}
        )
        == "concat(get('fields.field_2'),get('fields.field_13'))"
    )


@pytest.mark.field_ai
def test_field_id_references_invalid_id():
    with pytest.raises(KeyError):
        replace_field_id_references("get('fields.field_1')", {})


@pytest.mark.field_ai
def test_field_id_references_invalid_formula():
    with pytest.raises(BaserowFormulaSyntaxError):
        replace_field_id_references("get('fields.field_1'))", {})


@pytest.mark.django_db
def test_get_ai_prompt_error_returns_none_for_empty_prompt(premium_data_fixture):
    table = premium_data_fixture.create_database_table()
    assert get_ai_prompt_error("", table) is None


@pytest.mark.django_db
def test_get_ai_prompt_error_returns_none_for_valid_reference(premium_data_fixture):
    table = premium_data_fixture.create_database_table()
    text_field = premium_data_fixture.create_text_field(table=table)
    prompt = f"concat('Hi ', get('fields.field_{text_field.id}'))"
    assert get_ai_prompt_error(prompt, table) is None


@pytest.mark.django_db
def test_get_ai_prompt_error_detects_unparseable_prompt(premium_data_fixture):
    table = premium_data_fixture.create_database_table()
    # Unbalanced parenthesis -> BaserowFormulaSyntaxError.
    assert get_ai_prompt_error("concat('a', ", table) is not None


@pytest.mark.django_db
def test_get_ai_prompt_error_detects_missing_field_reference(premium_data_fixture):
    table = premium_data_fixture.create_database_table()
    # field_999999 does not exist in this table.
    prompt = "get('fields.field_999999')"
    assert get_ai_prompt_error(prompt, table) is not None


@pytest.mark.django_db
def test_get_ai_prompt_error_detects_reference_to_other_table_field(
    premium_data_fixture,
):
    table = premium_data_fixture.create_database_table()
    other_table = premium_data_fixture.create_database_table()
    other_field = premium_data_fixture.create_text_field(table=other_table)
    prompt = f"get('fields.field_{other_field.id}')"
    assert get_ai_prompt_error(prompt, table) is not None
