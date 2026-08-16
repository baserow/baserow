import pytest

from baserow.contrib.database.fields.formula_visitors import (
    extract_field_id_dependencies,
    get_table_field_ids,
    replace_field_id_references,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.cache import local_cache


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


def test_replace_field_id_references_with_incomplete_get_calls():
    # `get()` and `get('fields')` both pass the create API, so remapping them
    # must not crash the import or duplication job they run inside.
    assert replace_field_id_references("get()", {1: 2}) == "get()"
    assert replace_field_id_references("get('fields')", {1: 2}) == "get('fields')"
    assert (
        replace_field_id_references("concat('x',get('fields'))", {1: 2})
        == "concat('x',get('fields'))"
    )


def test_extract_field_id_dependencies_skips_raw_formulas():
    assert (
        extract_field_id_dependencies(
            {"formula": "get('fields.field_1')", "mode": "raw"}
        )
        == set()
    )


def test_extract_field_id_dependencies():
    assert extract_field_id_dependencies(
        "concat(get('fields.field_1'), get('fields.field_3'))"
    ) == {1, 3}
    assert extract_field_id_dependencies("") == set()


@pytest.mark.django_db
def test_get_table_field_ids_is_cached_per_table(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    field = data_fixture.create_text_field(table=table)

    with local_cache.context():
        # The second read reuses the cached ids.
        with django_assert_num_queries(1):
            assert get_table_field_ids(table.id) == {field.id}
            assert get_table_field_ids(table.id) == {field.id}


@pytest.mark.django_db
def test_get_table_field_ids_cache_is_invalidated_on_schema_change(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    with local_cache.context():
        assert get_table_field_ids(table.id) == {field.id}

        # Trashing the field sends `table_schema_changed`, so the cached ids
        # must not keep reporting it as still there.
        FieldHandler().delete_field(user, field)
        assert get_table_field_ids(table.id) == set()
