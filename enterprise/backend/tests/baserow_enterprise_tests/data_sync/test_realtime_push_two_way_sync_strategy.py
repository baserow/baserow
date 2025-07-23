import pytest

from django.test.utils import override_settings


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_enable_two_way_data_sync_strategy_without_enterprise_license():
    assert False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_is_updated_after_creating_a_row():
    assert False
