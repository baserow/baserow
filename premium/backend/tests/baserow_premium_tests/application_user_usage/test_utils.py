from unittest.mock import patch

import pytest

from baserow.core.cache import global_cache
from baserow_premium.application_user_usage.utils import (
    INSTANCE_WIDE_APPLICATION_USER_COUNT_CACHE_KEY,
    get_instance_wide_application_user_count,
)


@pytest.mark.django_db
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_instance_wide_application_user_count_is_cached(
    mock_aggregate_user_source_counts,
):
    mock_aggregate_user_source_counts.return_value = 7

    # The count is only resolved once for as long as it's cached, so the periodic
    # limit check doesn't recount every published user source in the instance for
    # each workspace it checks.
    assert get_instance_wide_application_user_count() == 7
    assert get_instance_wide_application_user_count() == 7
    assert mock_aggregate_user_source_counts.call_count == 1

    # Unlike the local cache this used to use, the count survives the request or
    # celery task that resolved it, and is only recounted once the cache entry is
    # gone.
    mock_aggregate_user_source_counts.return_value = 9
    assert get_instance_wide_application_user_count() == 7

    global_cache.invalidate(INSTANCE_WIDE_APPLICATION_USER_COUNT_CACHE_KEY)
    assert get_instance_wide_application_user_count() == 9
    assert mock_aggregate_user_source_counts.call_count == 2
