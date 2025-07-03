from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.table.cache import get_cached_model_field_attrs
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
def test_creating_link_row_field_invalidates_its_link_row_related_cache(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    unrelated_table = data_fixture.create_database_table(user=user)
    table_a = data_fixture.create_database_table(user=user)
    table_b = data_fixture.create_database_table(user=user, database=table_a.database)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version
    old_unrelated_table_version = unrelated_table.version

    FieldHandler().create_field(
        user, table_a, "link_row", link_row_table=table_b, name="new"
    )

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    unrelated_table.refresh_from_db()
    assert old_table_a_version != table_a.version
    assert old_table_b_version != table_b.version
    assert old_unrelated_table_version == unrelated_table.version


@pytest.mark.django_db
def test_converting_link_row_field_to_another_type_invalidates_its_related_tables_cache(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version

    FieldHandler().update_field(user, link_field, new_type_name="text")

    table_a.refresh_from_db()
    assert table_a.version != old_table_a_version

    table_b.refresh_from_db()
    assert table_b.version != old_table_b_version


@pytest.mark.django_db
def test_converting_link_row_field_to_point_at_another_table_invalidates_its_related_tables_cache(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    table_c = data_fixture.create_database_table(user, database=table_a.database)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    table_c.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version
    old_table_c_version = table_c.version

    FieldHandler().update_field(user, link_field, link_row_table=table_c)

    table_a.refresh_from_db()
    assert table_a.version != old_table_a_version

    table_b.refresh_from_db()
    assert table_b.version != old_table_b_version

    table_c.refresh_from_db()
    assert table_c.version != old_table_c_version


@pytest.mark.django_db
def test_converting_text_to_link_row_field_invalidates_its_related_tables_cache(
    data_fixture,
):
    user = data_fixture.create_user()
    unrelated_table = data_fixture.create_database_table(user=user)
    table_a = data_fixture.create_database_table(user=user)
    table_b = data_fixture.create_database_table(user=user, database=table_a.database)
    table_a_text_field = data_fixture.create_text_field(table=table_a)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version
    old_unrelated_table_version = unrelated_table.version

    FieldHandler().update_field(
        user, table_a_text_field, "link_row", link_row_table=table_b, name="new"
    )

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    unrelated_table.refresh_from_db()
    assert old_table_a_version != table_a.version
    assert old_table_b_version != table_b.version
    assert old_unrelated_table_version == unrelated_table.version


@pytest.mark.django_db
@override_settings(BASEROW_DISABLE_MODEL_CACHE=True)
def test_can_disable_model_cache(
    data_fixture,
):
    user = data_fixture.create_user()
    unrelated_table = data_fixture.create_database_table(user=user)
    table_a = data_fixture.create_database_table(user=user)
    table_b = data_fixture.create_database_table(user=user, database=table_a.database)
    table_a_text_field = data_fixture.create_text_field(table=table_a)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version
    old_unrelated_table_version = unrelated_table.version

    assert get_cached_model_field_attrs(table_a) is None
    assert get_cached_model_field_attrs(table_b) is None
    assert get_cached_model_field_attrs(unrelated_table) is None

    FieldHandler().update_field(
        user, table_a_text_field, "link_row", link_row_table=table_b, name="new"
    )

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    unrelated_table.refresh_from_db()
    assert old_table_a_version == table_a.version
    assert old_table_b_version == table_b.version
    assert old_unrelated_table_version == unrelated_table.version

    assert get_cached_model_field_attrs(table_a) is None
    assert get_cached_model_field_attrs(table_b) is None
    assert get_cached_model_field_attrs(unrelated_table) is None


@pytest.mark.django_db
def test_trashing_link_row_field_invalidates_its_related_tables_cache(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version

    FieldHandler().delete_field(user, link_field)

    table_a.refresh_from_db()
    assert table_a.version != old_table_a_version

    table_b.refresh_from_db()
    assert table_b.version != old_table_b_version


@pytest.mark.django_db
def test_restoring_link_row_field_invalidates_its_related_tables_cache(
    data_fixture,
):
    user = data_fixture.create_user()
    table_a, table_b, link_field = data_fixture.create_two_linked_tables(user=user)

    FieldHandler().delete_field(user, link_field)

    table_a.refresh_from_db()
    table_b.refresh_from_db()
    old_table_a_version = table_a.version
    old_table_b_version = table_b.version

    TrashHandler().restore_item(user, "field", link_field.id)

    table_a.refresh_from_db()
    assert table_a.version != old_table_a_version

    table_b.refresh_from_db()
    assert table_b.version != old_table_b_version


@pytest.mark.django_db
def test_deleting_field_invalidates_tables_model_cache(data_fixture):
    field = data_fixture.create_text_field()
    table = field.table
    field.table.get_model()

    assert get_cached_model_field_attrs(table) is not None

    field.delete()

    table.refresh_from_db()
    assert get_cached_model_field_attrs(table) is None
