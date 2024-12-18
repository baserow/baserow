import zoneinfo
from functools import lru_cache


@lru_cache(maxsize=None)
def get_timezones():
    return zoneinfo.available_timezones()
