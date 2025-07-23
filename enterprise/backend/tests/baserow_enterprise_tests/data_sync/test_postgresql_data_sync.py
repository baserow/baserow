import pytest

from django.test.utils import override_settings


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_row_in_postgresql_table():
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_unique_primary_is_updated_after_creating_a_row():
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_row_in_postgresql_table():
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_row_in_postgresql_table():
    assert False
