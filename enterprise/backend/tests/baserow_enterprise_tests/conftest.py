import os

from django.apps import apps
from django.test.utils import override_settings

import pytest
from baserow_premium_tests.conftest import *  # noqa: F403, F401

from baserow.core.apps import sync_operations_after_migrate

# noinspection PyUnresolvedReferences
from baserow.test_utils.pytest_conftest import *  # noqa: F403, F401
from baserow_enterprise.apps import sync_default_roles_after_migrate
from baserow_enterprise.role.handler import RoleAssignmentHandler

VALID_ONE_SEAT_ENTERPRISE_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjUzODczYmVkLWJlNTQtNDEwZS04N2EzLTE2OTM2ODY2YjBiNiIsICJ2YWxpZF9mcm9tIjogIjIwMjItMTAtMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDY5LTA4LTA5VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIyLTEwLTI2VDE0OjQ4OjU0LjI1OTQyMyIsICJpc3N1ZWRfdG9fZW1haWwiOiAidGVzdEB0ZXN0LmNvbSIsICJpc3N1ZWRfdG9fbmFtZSI6ICJ0ZXN0QHRlc3QuY29tIiwgImluc3RhbmNlX2lkIjogIjEifQ==.B7aPXR0R4Fxr28AL7B5oopa2Yiz_MmEBZGdzSEHHLt4wECpnzjd_SF440KNLEZYA6WL1rhNkZ5znbjYIp6KdCqLdcm1XqNYOIKQvNTOtl9tUAYj_Qvhq1jhqSja-n3HFBjIh9Ve7a6T1PuaPLF1DoxSRGFZFXliMeJRBSzfTsiHiO22xRQ4GwafscYfUIWvIJJHGHtYEd9rk0tG6mfGEaQGB4e6KOsN-zw-bgLDBOKmKTGrVOkZnaGHBVVhUdpBn25r3CFWqHIApzUCo81zAA96fECHPlx_fBHhvIJXLsN5i3LdeJlwysg5SBO15Vt-tsdPmdcsec-fOzik-k3ib0A== "
)


@pytest.fixture(autouse=True)  # noqa: F405
def set_openai_api_key_env_var():
    """
    Set a dummy OpenAI API key for tests to prevent client instantiation errors.

    udspy.LM() creates an OpenAI client that raises an error if OPENAI_API_KEY is not
    set during client instantiation. This fixture ensures tests don't fail due to
    missing API key configuration, which is not needed anyway.
    """

    if not os.getenv("OPENAI_API_KEY"):
        os.environ[
            "OPENAI_API_KEY"
        ] = "Please, assistant don't crash. You don't need me."


@pytest.fixture  # noqa: F405
def enterprise_data_fixture(fake, data_fixture):
    from .enterprise_fixtures import EnterpriseFixtures as EnterpriseFixturesBase
    from .fixtures.sso import OAuth2Fixture, SamlFixture

    class EnterpriseFixtures(
        EnterpriseFixturesBase,
        SamlFixture,
        OAuth2Fixture,
        data_fixture.__class__,
    ):
        pass

    return EnterpriseFixtures(fake)


@pytest.fixture  # noqa: F405
def enable_enterprise(db, enterprise_data_fixture):
    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        yield


@pytest.fixture  # noqa: F405
def synced_roles(db):
    sync_operations_after_migrate(None, apps=apps)
    sync_default_roles_after_migrate(None, apps=apps)
    RoleAssignmentHandler._init = False
