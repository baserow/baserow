from collections import defaultdict
from typing import Dict, Generator, List, Set, Union
from unittest.mock import patch

from django.contrib.auth.models import AbstractUser

# noinspection PyUnresolvedReferences
import pytest
from baserow_premium.license.license_types import PremiumLicenseType
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.license.registries import LicenseType, license_type_registry
from baserow_premium.plugins import PremiumPlugin
from fakeredis import FakeRedis, FakeServer

from baserow.core.cache import local_cache
from baserow.test_utils.pytest_conftest import *  # noqa: F403, F401


@pytest.fixture(scope="function", autouse=True)
def mock_periodic_field_update_handler_redis_client():
    redis_client_fn = "baserow.contrib.database.fields.periodic_field_update_handler._get_redis_client"
    fake_redis_server = FakeServer()
    with patch(
        redis_client_fn, lambda: FakeRedis(server=fake_redis_server)
    ) as _fixture:
        yield _fixture


@pytest.fixture
def premium_data_fixture(fake, data_fixture):
    from .fixtures import PremiumFixtures

    class PremiumFixtures(PremiumFixtures, data_fixture.__class__):
        pass

    return PremiumFixtures(fake)


@pytest.fixture
def mutable_plugin_registry():
    from baserow.core.registries import plugin_registry

    before = plugin_registry.registry.copy()
    yield plugin_registry
    plugin_registry.registry = before


class PerWorkspaceLicensePlugin(LicensePlugin):
    def __init__(self):
        super().__init__()
        self.per_workspace_licenses = defaultdict(lambda: defaultdict(set))

    def get_active_instance_wide_license_types(
        self, user: AbstractUser
    ) -> Generator[LicenseType, None, None]:
        return
        yield

    def get_active_per_workspace_licenses(
        self, user: AbstractUser
    ) -> Dict[int, Set[LicenseType]]:
        return self.per_workspace_licenses[user.id]

    def restrict_user_premium_to(
        self, user: AbstractUser, workspace_ids_or_id: Union[int, List[int]]
    ):
        self.restrict_user_license_to(
            user, PremiumLicenseType.type, workspace_ids_or_id
        )

    def restrict_user_license_to(
        self,
        user: AbstractUser,
        license_type: str,
        workspace_ids_or_id: Union[int, List[int]],
    ):
        if isinstance(workspace_ids_or_id, int):
            workspace_ids_or_id = [workspace_ids_or_id]
        self.per_workspace_licenses[user.id] = defaultdict(set)
        for workspace_id in workspace_ids_or_id:
            self.per_workspace_licenses[user.id][workspace_id].add(
                license_type_registry.get(license_type)
            )
        local_cache.clear()


class PremiumPluginWithPerWorkspaceLicensePlugin(PremiumPlugin):
    license_plugin = PerWorkspaceLicensePlugin()

    def get_license_plugin(self) -> LicensePlugin:
        return self.license_plugin


@pytest.fixture
def alternative_per_workspace_license_service(
    mutable_plugin_registry,
) -> PerWorkspaceLicensePlugin:
    """
    Overrides the existing license service with a test only stub version that
    allows configuring whether a user has premium features at a per workspace level.
    """

    stub_premium_plugin = PremiumPluginWithPerWorkspaceLicensePlugin()
    mutable_plugin_registry.registry[PremiumPlugin.type] = stub_premium_plugin

    yield stub_premium_plugin.get_license_plugin()
