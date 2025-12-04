from unittest.mock import patch

import pytest

from baserow_premium.license.handler import LicenseHandler


@pytest.mark.django_db
@patch.object(LicenseHandler, "check_licenses")
def test_license_check(check_licenses_handler_func_mock, premium_data_fixture):
    from baserow_premium.license.tasks import license_check

    license_check()

    assert not check_licenses_handler_func_mock.called

    premium_data_fixture.create_premium_license()
    license_check()

    assert check_licenses_handler_func_mock.called
