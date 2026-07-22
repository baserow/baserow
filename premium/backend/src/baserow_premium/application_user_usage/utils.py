from baserow.core.cache import local_cache
from baserow_premium.application_user_usage.handler import ApplicationUserUsageHandler


def get_instance_wide_application_user_count() -> int:
    """
    Returns the instance wide application user count, memoized for the duration of
    the current local cache context (a single request or celery task).

    The periodic limit check resolves the same instance wide count once per
    workspace, so without this it would recount every published user source in the
    instance for each workspace it checks.

    :return: The number of application users in the instance.
    """

    return local_cache.get(
        "instance_wide_application_user_count",
        lambda: ApplicationUserUsageHandler().aggregate_user_source_counts(),
    )
