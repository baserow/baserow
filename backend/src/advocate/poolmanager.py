import collections
import functools

from urllib3 import PoolManager
from urllib3.poolmanager import PoolKey, _default_key_normalizer

from .connectionpool import (
    ValidatingHTTPConnectionPool,
    ValidatingHTTPSConnectionPool,
)

pool_classes_by_scheme = {
    "http": ValidatingHTTPConnectionPool,
    "https": ValidatingHTTPSConnectionPool,
}

AdvocatePoolKey = collections.namedtuple(
    "AdvocatePoolKey", PoolKey._fields + ("key_validator",)
)


def key_normalizer(key_class, request_context):
    request_context = request_context.copy()
    # TODO: add ability to serialize validator rules to dict,
    # allowing pool to be shared between sessions with the same
    # rules.
    request_context["validator"] = id(request_context["validator"])
    return _default_key_normalizer(key_class, request_context)


key_fn_by_scheme = {
    "http": functools.partial(key_normalizer, AdvocatePoolKey),
    "https": functools.partial(key_normalizer, AdvocatePoolKey),
}


class ValidatingPoolManager(PoolManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make sure the API hasn't changed
        assert hasattr(self, "pool_classes_by_scheme")

        self.pool_classes_by_scheme = pool_classes_by_scheme
        self.key_fn_by_scheme = key_fn_by_scheme.copy()
