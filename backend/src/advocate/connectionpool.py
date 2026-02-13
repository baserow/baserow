from urllib3 import HTTPConnectionPool, HTTPSConnectionPool

from .connection import (
    ValidatingHTTPConnection,
    ValidatingHTTPSConnection,
)

# Don't silently break if the private API changes across urllib3 versions
assert hasattr(HTTPConnectionPool, "ConnectionCls")
assert hasattr(HTTPSConnectionPool, "ConnectionCls")
assert hasattr(HTTPConnectionPool, "scheme")
assert hasattr(HTTPSConnectionPool, "scheme")


class ValidatingHTTPConnectionPool(HTTPConnectionPool):
    scheme = "http"
    ConnectionCls = ValidatingHTTPConnection


class ValidatingHTTPSConnectionPool(HTTPSConnectionPool):
    scheme = "https"
    ConnectionCls = ValidatingHTTPSConnection
