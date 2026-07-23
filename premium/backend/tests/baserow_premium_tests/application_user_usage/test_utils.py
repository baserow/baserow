from unittest.mock import patch

from baserow.core.cache import local_cache
from baserow_premium.application_user_usage.utils import (
    get_instance_wide_application_user_count,
)


@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_instance_wide_application_user_count_is_memoized_per_context(
    mock_aggregate_user_source_counts,
):
    mock_aggregate_user_source_counts.return_value = 7

    # Within one local cache context (a single request or celery task) the count
    # is only resolved once, so the periodic limit check doesn't recount every
    # published user source in the instance for each workspace it checks.
    with local_cache.context():
        assert get_instance_wide_application_user_count() == 7
        assert get_instance_wide_application_user_count() == 7
        assert mock_aggregate_user_source_counts.call_count == 1

    # A fresh context recounts.
    with local_cache.context():
        assert get_instance_wide_application_user_count() == 7
        assert mock_aggregate_user_source_counts.call_count == 2
