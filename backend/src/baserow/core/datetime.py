import zoneinfo
from datetime import datetime
from functools import lru_cache


@lru_cache(maxsize=None)
def get_timezones():
    return zoneinfo.available_timezones()


def get_current_hourly_quarter() -> int:
    """
    Returns the current hourly quarter based on the current minute. The quarter is
    calculated by dividing the current minute by 15.
    """

    minutes = datetime.now().minute
    if 0 <= minutes < 15:
        return 0
    elif 15 <= minutes < 30:
        return 1
    elif 30 <= minutes < 45:
        return 2
    elif 45 <= minutes < 60:
        return 3
