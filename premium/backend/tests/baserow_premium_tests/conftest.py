from collections import defaultdict
from typing import Dict, Generator, List, Set, Union

from django.contrib.auth.models import AbstractUser

# noinspection PyUnresolvedReferences
import pytest
from baserow_premium.license.license_types import PremiumLicenseType
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.license.registries import LicenseType, license_type_registry
from baserow_premium.plugins import PremiumPlugin

from baserow.core.cache import local_cache
from baserow.test_utils.pytest_conftest import *  # noqa: F403, F401, F405


@pytest.fixture
def premium_data_fixture(fake, data_fixture):
    from .dashboard.dashboard_fixtures import DashboardFixture
    from .fixtures import PremiumFixtures

    class PremiumFixtures(DashboardFixture, PremiumFixtures, data_fixture.__class__):
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


@pytest.fixture(scope="function", autouse=True)
def patch_aigeneratorworker_pool():
    """
    Patches thread-based executor for AI value generation with a serialized execution,
    so we run each worker in the main thread, and have proper access to test database.
    """

    class SerialExecutor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def submit(self, call, *args, **kwargs):
            try:
                call(*args, **kwargs)
            except Exception as err:
                logger.opt(exception=err).warning(  # noqa: F405
                    f" SerialExecutor call {call}({args}, {kwargs}) failed: {err}"
                )

    def patch_executor(*args, **kwargs):
        return SerialExecutor()

    with patch(  # noqa: F405
        "baserow_premium.fields.job_types.get_executor", new=patch_executor
    ) as patched:
        yield patched
