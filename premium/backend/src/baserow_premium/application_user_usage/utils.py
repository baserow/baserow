from baserow.core.cache import global_cache
from baserow_premium.application_user_usage.handler import ApplicationUserUsageHandler

INSTANCE_WIDE_APPLICATION_USER_COUNT_CACHE_KEY = "instance_wide_application_user_count"


def get_instance_wide_application_user_count() -> int:
    """
    Returns the instance wide application user count, cached for 30 minutes.

    The periodic limit check resolves the same instance wide count once per
    workspace, so without this it would recount every published user source in the
    instance for each workspace it checks.

    :return: The number of application users in the instance.
    """

    return global_cache.get(
        INSTANCE_WIDE_APPLICATION_USER_COUNT_CACHE_KEY,
        default=lambda: ApplicationUserUsageHandler().aggregate_user_source_counts(),
        timeout=60 * 30,  # 30 minutes
    )
