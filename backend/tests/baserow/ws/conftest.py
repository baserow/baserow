import os

import pytest
from fakeredis.aioredis import FakeRedis

from baserow.config.settings.test import _fake_redis_server
from baserow.core.async_redis import set_async_redis
from baserow.ws.registries import PageType, page_registry

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(autouse=True)
def _inject_fake_async_redis():
    """
    Inject a FakeRedis async client sharing the same FakeServer as
    django-redis (sync) so both sync assertions and async production
    code hit the same in-memory store.
    """

    client = FakeRedis(server=_fake_redis_server, decode_responses=True)
    set_async_redis(client)
    yield
    set_async_redis(None)


class PresenceTestPageType(PageType):
    type = "test_presence_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-presence-page-{test_param}"

    def get_presence_space_name(self, test_param, **kwargs):
        return f"test-space-{test_param}"

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type):
        return True


class NonPresencePageType(PageType):
    type = "test_non_presence_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-non-presence-page-{test_param}"


class DenyFocusPageType(PageType):
    """Shares presence spaces with PresenceTestPageType but denies all focus."""

    type = "test_presence_deny_focus_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-deny-focus-page-{test_param}"

    def get_presence_space_name(self, test_param, **kwargs):
        return f"test-space-{test_param}"

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type):
        return False


class DefaultFilterPageType(PageType):
    """Presence-enabled page type relying on the base fail-closed filter."""

    type = "test_presence_default_filter_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-default-filter-page-{test_param}"

    def get_presence_space_name(self, test_param, **kwargs):
        return f"test-space-{test_param}"


class PresenceWithPermGroupPageType(PageType):
    type = "test_presence_perm_page"
    parameters = ["test_param"]

    def can_add(self, user, web_socket_id, test_param, **kwargs):
        return True

    def get_group_name(self, test_param, **kwargs):
        return f"test-presence-perm-page-{test_param}"

    def get_permission_channel_group_name(self, test_param, **kwargs):
        return f"test-perm-group-{test_param}"

    def get_presence_space_name(self, test_param, **kwargs):
        return f"test-perm-space-{test_param}"

    def filter_focus_for_recipient(self, page_parameters, focus, focus_type):
        return True


@pytest.fixture
def presence_types():
    page_registry.register(PresenceTestPageType())
    page_registry.register(NonPresencePageType())
    page_registry.register(DenyFocusPageType())
    page_registry.register(DefaultFilterPageType())
    page_registry.register(PresenceWithPermGroupPageType())
    yield

    page_registry.unregister(PresenceTestPageType.type)
    page_registry.unregister(NonPresencePageType.type)
    page_registry.unregister(DenyFocusPageType.type)
    page_registry.unregister(DefaultFilterPageType.type)
    page_registry.unregister(PresenceWithPermGroupPageType.type)
