"""
advocate.api
~~~~~~~~~~~~

This module implements the Requests API, largely a copy/paste from `requests`
itself.

:copyright: (c) 2015 by Jordan Milne.
:license: Apache2, see LICENSE for more details.

"""

import hashlib
import pickle
from collections import OrderedDict

from requests import Session as RequestsSession

import advocate

from .adapters import ValidatingHTTPAdapter
from .exceptions import MountDisabledException


class Session(RequestsSession):
    """Convenience wrapper around `requests.Session` set up for `advocate`ing"""

    __attrs__ = RequestsSession.__attrs__ + ["validator"]
    DEFAULT_VALIDATOR = None
    """
    User-replaceable default validator to use for all Advocate sessions,
    includes sessions created by advocate.get()
    """

    def __init__(self, *args, **kwargs):
        self.validator = kwargs.pop("validator", None) or self.DEFAULT_VALIDATOR
        adapter_kwargs = kwargs.pop("_adapter_kwargs", {})

        # `Session.__init__()` calls `mount()` internally, so we need to allow
        # it temporarily
        self.__mount_allowed = True
        RequestsSession.__init__(self, *args, **kwargs)

        # Drop any existing adapters
        self.adapters = OrderedDict()

        self.mount(
            "http://", ValidatingHTTPAdapter(validator=self.validator, **adapter_kwargs)
        )
        self.mount(
            "https://",
            ValidatingHTTPAdapter(validator=self.validator, **adapter_kwargs),
        )
        self.__mount_allowed = False

    def mount(self, *args, **kwargs):
        """Wrapper around `mount()` to prevent a protection bypass"""
        if self.__mount_allowed:
            super().mount(*args, **kwargs)
        else:
            raise MountDisabledException(
                "mount() is disabled to prevent protection bypasses"
            )


def session(*args, **kwargs):
    return Session(*args, **kwargs)


def request(method, url, **kwargs):
    """Constructs and sends a :class:`Request <Request>`.

    :param method: method for the new :class:`Request` object.
    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query string for the :class:`Request`.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param json: (optional) json data to send in the body of the :class:`Request`.
    :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
    :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
    :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': ('filename', fileobj)}``) for multipart encoding upload.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.
    :param timeout: (optional) How long to wait for the server to send data
        before giving up, as a float, or a (`connect timeout, read timeout
        <user/advanced.html#timeouts>`_) tuple.
    :type timeout: float or tuple
    :param allow_redirects: (optional) Boolean. Set to True if POST/PUT/DELETE redirect following is allowed.
    :type allow_redirects: bool
    :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
    :param verify: (optional) if ``True``, the SSL cert will be verified. A CA_BUNDLE path can also be provided.
    :param stream: (optional) if ``False``, the response content will be immediately downloaded.
    :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response

    Usage::

      >>> import advocate
      >>> req = advocate.request('GET', 'http://httpbin.org/get')
      <Response [200]>
    """

    validator = kwargs.pop("validator", None)
    with Session(validator=validator) as sess:
        response = sess.request(method=method, url=url, **kwargs)
    return response


def get(url, **kwargs):
    r"""Sends a GET request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault("allow_redirects", True)
    return request("get", url, **kwargs)


def options(url, **kwargs):
    r"""Sends a OPTIONS request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault("allow_redirects", True)
    return request("options", url, **kwargs)


def head(url, **kwargs):
    r"""Sends a HEAD request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault("allow_redirects", False)
    return request("head", url, **kwargs)


def post(url, data=None, json=None, **kwargs):
    r"""Sends a POST request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param json: (optional) json data to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("post", url, data=data, json=json, **kwargs)


def put(url, data=None, **kwargs):
    r"""Sends a PUT request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("put", url, data=data, **kwargs)


def patch(url, data=None, **kwargs):
    r"""Sends a PATCH request.

    :param url: URL for the new :class:`Request` object.
    :param data: (optional) Dictionary, bytes, or file-like object to send in the body of the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("patch", url, data=data, **kwargs)


def delete(url, **kwargs):
    r"""Sends a DELETE request.

    :param url: URL for the new :class:`Request` object.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    return request("delete", url, **kwargs)


class RequestsAPIWrapper:
    """Provides a `requests.api`-like interface with a specific validator"""

    # Due to how the classes are dynamically constructed pickling may not work
    # correctly unless loaded within the same interpreter instance.
    # Enable at your peril.
    SUPPORT_WRAPPER_PICKLING = False

    def __init__(self, validator):
        # Do this here to avoid circular import issues
        try:
            from .futures import FuturesSession

            have_requests_futures = True
        except ImportError:
            have_requests_futures = False

        self.validator = validator
        outer_self = self

        class _WrappedSession(Session):
            """An `advocate.Session` that uses the wrapper's blacklist

            the wrapper is meant to be a transparent replacement for `requests`,
            so people should be able to subclass `wrapper.Session` and still
            get the desired validation behaviour
            """

            DEFAULT_VALIDATOR = outer_self.validator

        self._make_wrapper_cls_global(_WrappedSession)

        if have_requests_futures:

            class _WrappedFuturesSession(FuturesSession):
                """Like _WrappedSession, but for `FuturesSession`s"""

                DEFAULT_VALIDATOR = outer_self.validator

            self._make_wrapper_cls_global(_WrappedFuturesSession)

            self.FuturesSession = _WrappedFuturesSession

        self.request = self._default_arg_wrapper(request)
        self.get = self._default_arg_wrapper(get)
        self.options = self._default_arg_wrapper(options)
        self.head = self._default_arg_wrapper(head)
        self.post = self._default_arg_wrapper(post)
        self.put = self._default_arg_wrapper(put)
        self.patch = self._default_arg_wrapper(patch)
        self.delete = self._default_arg_wrapper(delete)
        self.session = self._default_arg_wrapper(session)
        self.Session = _WrappedSession

    def __getattr__(self, item):
        # This class is meant to mimic the requests base module, so if we don't
        # have this attribute, it might be on the base module (like the Request
        # class, etc.)
        try:
            return object.__getattribute__(self, item)
        except AttributeError:
            return getattr(advocate, item)

    def _default_arg_wrapper(self, fun):
        def wrapped_func(*args, **kwargs):
            kwargs.setdefault("validator", self.validator)
            return fun(*args, **kwargs)

        return wrapped_func

    def _make_wrapper_cls_global(self, cls):
        if not self.SUPPORT_WRAPPER_PICKLING:
            return
        # Gnarly, but necessary to give pickle a consistent module-level
        # reference for each wrapper.
        wrapper_hash = hashlib.sha256(pickle.dumps(self)).hexdigest()
        cls.__name__ = "_".join((cls.__name__, wrapper_hash))
        cls.__qualname__ = ".".join((__name__, cls.__name__))
        if not globals().get(cls.__name__):
            globals()[cls.__name__] = cls


__all__ = (
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "put",
    "request",
    "session",
    "Session",
    "RequestsAPIWrapper",
)
