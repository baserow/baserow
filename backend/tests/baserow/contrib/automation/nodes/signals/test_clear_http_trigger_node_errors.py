from uuid import uuid4

import pytest

from baserow.contrib.automation.nodes.signals import automation_node_updated
from baserow.contrib.integrations.core.api.webhooks.views import get_error_cache_key
from baserow.contrib.integrations.core.exceptions import (
    CoreHTTPTriggerServiceDoesNotExist,
    CoreHTTPTriggerServiceMethodNotAllowed,
)
from baserow.core.cache import global_cache


@pytest.mark.django_db
@pytest.mark.parametrize(
    "service_class",
    [
        CoreHTTPTriggerServiceDoesNotExist,
        CoreHTTPTriggerServiceMethodNotAllowed,
    ],
)
def test_clears_http_trigger_error_cache_when_node_is_updated(
    data_fixture, service_class
):
    for simulate in [True, False]:
        # Set an error in the cache
        uuid = uuid4()
        cache_key = get_error_cache_key(uuid, simulate)
        global_cache.get(cache_key, service_class.__name__, timeout=10)

        service = data_fixture.create_core_http_trigger_service(uid=uuid)
        node = data_fixture.create_automation_node(service=service)

        # Ensure the initial check is a cache-hit
        cache_exists = global_cache.get(cache_key, default=None, timeout=0)
        assert bool(cache_exists) is True

        # Send a signal that the workflow has been published
        automation_node_updated.send(None, user=None, node=node)

        # Make sure the cache has been cleared
        cache_exists = global_cache.get(cache_key, default=None, timeout=0)
        assert bool(cache_exists) is False
