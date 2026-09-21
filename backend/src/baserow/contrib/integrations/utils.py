import contextlib
import contextvars
import heapq
import itertools
import os
import socket
import sys
import threading
import time
from typing import Optional

from django.conf import settings

import requests
from loguru import logger
from requests import exceptions as request_exceptions
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import (
    ConnectTimeoutError,
    DecodeError,
    LocationParseError,
    NameResolutionError,
    NewConnectionError,
    ProtocolError,
    ReadTimeoutError,
    SSLError,
)
from urllib3.util.connection import _set_socket_options, allowed_gai_family
from urllib3.util.timeout import _DEFAULT_TIMEOUT

import advocate
from advocate.connection import (
    ValidatingHTTPConnection,
    ValidatingHTTPSConnection,
    attempt_timeout,
)
from advocate.connectionpool import (
    ValidatingHTTPConnectionPool,
    ValidatingHTTPSConnectionPool,
)
from baserow.core.services.exceptions import ResponseTooLargeDispatchException


def _read_body(response, request_deadline: "_RequestDeadline") -> None:
    """
    Pulls the body in with a ceiling on its size and a deadline on how long it
    may take, and hangs up on an endpoint that goes past either.

    Buffering it whole and measuring afterwards is too late: the memory is
    already spent. The size ceiling is on what arrives after decompression, so
    a small answer that unpacks into a big one is caught. The deadline is wall
    clock, unlike the timeout Requests applies, which only starts again on
    every byte: a server sending one every few seconds would otherwise hold
    the dispatch open for as long as it liked, past the lock that guards the
    row.

    :param response: The streamed response.
    :param request_deadline: The request the response belongs to: the body
        must have arrived by its deadline, and its watchdog may hang up mid
        read.
    :raises ResponseTooLargeDispatchException: When the body is larger than the
        ceiling.
    :raises requests.exceptions.Timeout: When it takes longer than the
        deadline, or a single read times out.
    """

    # Read whatever the ceiling is set to. Returning early with the ceiling
    # off would leave the body unread under `stream=True`, so `response.json()`
    # would pull it in later, outside the block that maps a truncated or
    # corrupt answer onto a message the caller can use, and the deadline below
    # would never be armed either.
    max_bytes = settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES or None

    content = bytearray()

    deadline = request_deadline.deadline

    def timed_out():
        return request_deadline.hung_up or time.monotonic() > deadline

    try:
        while True:
            try:
                # `read1` hands back whatever has arrived, however little, so
                # the deadline below is checked as the body comes in. Reading
                # `raw` skips the translation `iter_content` does, so its
                # errors are translated here.
                chunk = response.raw.read1(64 * 1024, decode_content=True)
            except ReadTimeoutError as e:
                raise request_exceptions.Timeout(e) from e
            except ProtocolError as e:
                # The deadline watchdog hanging up the socket can surface here
                # as a broken connection rather than as `read1` simply
                # returning nothing, so it is answered the same way.
                if timed_out():
                    raise request_exceptions.Timeout(e) from e
                raise request_exceptions.ConnectionError(e) from e
            except SSLError as e:
                # `SSLError` subclasses `HTTPError`, the same as
                # `ProtocolError`, not `ProtocolError` itself, so a broken TLS
                # record is not caught by the branch above; the deadline can
                # still be why the connection failed.
                if timed_out():
                    raise request_exceptions.Timeout(e) from e
                raise request_exceptions.SSLError(e) from e
            except DecodeError as e:
                # A compressed body cut off by the watchdog is incomplete, and
                # the decoder says so when `read1` reaches the end of it.
                if timed_out():
                    raise request_exceptions.Timeout(e) from e
                raise request_exceptions.ContentDecodingError(e) from e
            if not chunk:
                break
            content += chunk
            if max_bytes is not None and len(content) > max_bytes:
                raise ResponseTooLargeDispatchException(
                    f"The response is larger than the {max_bytes} bytes this "
                    f"installation accepts."
                )
            if time.monotonic() > deadline:
                raise request_exceptions.Timeout(
                    "The response body did not arrive in time."
                )
        # The watchdog hanging up the socket can also end the loop above: a
        # shut-down connection makes `read1` return an empty chunk, which
        # looks the same here as a body that finished normally, so a body cut
        # short past the deadline is still caught.
        if timed_out():
            raise request_exceptions.Timeout(
                "The response body did not arrive in time."
            )
    finally:
        response.close()

    # What `response.json()` and `response.text` read, so the rest of the
    # dispatch is unchanged.
    response._content = bytes(content)
    response._content_consumed = True


# Enough for http to https to a canonical host to a locale. The deadline is what
# bounds how long a request takes; this only stops an endless chain early.
MAX_REDIRECTS = 10

# The one thread that hangs up requests past their deadline, named so it can be
# told apart in a thread dump.
DEADLINE_WATCHDOG_THREAD_NAME = "http-request-deadline"


class _RequestDeadline:
    """
    What the watchdog needs to hang up one request: its deadline and a
    duplicate of every socket it opened.

    A duplicate rather than the connection: http.client lets go of a
    connection's socket as soon as it sees an answer that is read until the
    server closes it, and hands it to the response. Shutting the duplicate
    down cuts the same TCP connection off whoever holds the socket. It is a
    plain `socket.socket` even under TLS, so it leaves the `SSLSocket` a read
    may be blocked on in another thread alone.

    Holds nothing that refers back to the response, so a response carrying it
    is freed as soon as the caller drops it.
    """

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.hung_up = False
        self._finished = False
        self._sockets = []
        # The duplicates are only shut down and only closed under this lock,
        # and the watchdog never touches the caller's own sockets. A number
        # the operating system hands out again once a socket is closed can
        # therefore never be shut down in place of the one that was meant.
        self._lock = threading.Lock()

    def watch(self, sock: socket.socket) -> None:
        watched = socket.fromfd(sock.fileno(), sock.family, sock.type)
        with self._lock:
            # Record and check under one lock: a socket opened while the
            # watchdog hangs up is either shut down by it or sees `hung_up`.
            if not self.hung_up and not self._finished:
                self._sockets.append(watched)
                return
            if self.hung_up:
                try:
                    watched.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            watched.close()

    def hang_up(self) -> None:
        with self._lock:
            if self._finished:
                return
            self.hung_up = True
            for watched in self._sockets:
                # Neither may raise out of the loop, or the sockets after this
                # one would be left open.
                with contextlib.suppress(OSError):
                    watched.shutdown(socket.SHUT_RDWR)
                with contextlib.suppress(OSError):
                    watched.close()
            self._sockets.clear()

    def finish(self) -> None:
        with self._lock:
            if self._finished:
                return
            self._finished = True
            for watched in self._sockets:
                # Runs in `send_http_request`'s `finally`, where raising would
                # replace the response or the error the caller should see.
                with contextlib.suppress(OSError):
                    watched.close()
            self._sockets.clear()
        _watchdog.forget(self)


class _Watchdog:
    """
    One daemon thread for the process that hangs up every request still open
    at its deadline, earliest first, instead of a thread per request.
    """

    def __init__(self):
        self._reset()
        # A forked child has no watchdog thread, and a lock held by another
        # thread at the fork would never be released there.
        os.register_at_fork(after_in_child=self._reset)

    def _reset(self):
        self._condition = threading.Condition()
        self._heap = []
        self._counter = itertools.count()
        self._pid = None

    def watch(self, request_deadline: _RequestDeadline) -> None:
        with self._condition:
            if self._pid != os.getpid():
                threading.Thread(
                    target=self._run,
                    name=DEADLINE_WATCHDOG_THREAD_NAME,
                    daemon=True,
                ).start()
                self._pid = os.getpid()
            # The counter breaks ties between equal deadlines, which would
            # otherwise compare the states themselves.
            heapq.heappush(
                self._heap,
                (request_deadline.deadline, next(self._counter), request_deadline),
            )
            self._condition.notify()

    def forget(self, request_deadline: _RequestDeadline) -> None:
        with self._condition:
            for index, (_, _, pending) in enumerate(self._heap):
                if pending is request_deadline:
                    del self._heap[index]
                    heapq.heapify(self._heap)
                    break

    def pending_deadlines(self) -> list:
        with self._condition:
            return sorted(deadline for deadline, _, _ in self._heap)

    def _run(self):
        condition, heap = self._condition, self._heap
        while True:
            with condition:
                while True:
                    if not heap:
                        condition.wait()
                        continue
                    remaining = heap[0][0] - time.monotonic()
                    if remaining <= 0:
                        _, _, due = heapq.heappop(heap)
                        break
                    condition.wait(remaining)
            # Outside the condition, so a slow shutdown does not hold up
            # requests starting or finishing meanwhile.
            try:
                due.hang_up()
            except Exception as exc:
                # This is the only watchdog thread for the process: letting
                # one request's hang-up kill it would leave every later
                # deadline unenforced. Only the class is logged: loguru prints
                # frame locals beside a traceback, and a watched socket names
                # the address the request went to.
                logger.error(
                    "Failed to hang up a request past its deadline with {exception}.",
                    exception=type(exc).__name__,
                )


_watchdog = _Watchdog()


def _pending_deadlines() -> list:
    """The deadlines the watchdog is still waiting on, for the tests."""

    return _watchdog.pending_deadlines()


# Set by `send_http_request` around `session.request`, which opens every
# connection of the request, redirects included, on the calling thread. That is
# how a connection finds the request it belongs to without a class per request.
_current_request_deadline = contextvars.ContextVar(
    "current_request_deadline", default=None
)


def _create_connection(
    address: tuple,
    timeout,
    deadline: Optional[float],
    source_address=None,
    socket_options=None,
) -> socket.socket:
    """
    urllib3's `create_connection`, except that every attempt, across every
    address the host resolves to, only gets the time left until `deadline`.
    urllib3 hands each attempt the timeout the hop started with, so a host
    with several addresses that never answer would take one timeout per
    address. advocate's `validating_create_connection` does the same for the
    connections it validates.
    """

    host, port = address
    if host.startswith("["):
        host = host.strip("[]")
    try:
        host.encode("idna")
    except UnicodeError:
        raise LocationParseError(f"'{host}', label empty or too long") from None
    err = None
    for af, socktype, proto, _, sa in socket.getaddrinfo(
        host, port, allowed_gai_family(), socket.SOCK_STREAM
    ):
        sock = None
        try:
            sock = socket.socket(af, socktype, proto)
            _set_socket_options(sock, socket_options)
            if deadline is not None:
                sock.settimeout(attempt_timeout(timeout, deadline))
            elif timeout is not _DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            # Breaks the reference cycle through the traceback, as urllib3
            # does.
            err = None
            return sock
        except OSError as e:
            err = e
            if sock is not None:
                sock.close()
    if err is not None:
        try:
            raise err
        finally:
            err = None
    raise OSError("getaddrinfo returns an empty list")


class _WatchedConnectionMixin:
    # Read by the connect loop, which cannot see the request itself.
    connect_deadline = None

    def _new_conn(self):
        request_deadline = _current_request_deadline.get()
        if request_deadline is not None:
            self.connect_deadline = request_deadline.deadline
        # The plain TCP socket, before any TLS handshake or tunnel, so the
        # watchdog can hang up on those too.
        sock = super()._new_conn()
        if request_deadline is not None:
            request_deadline.watch(sock)
        return sock


class _DeadlineConnectMixin:
    """
    urllib3's `_new_conn` with `_create_connection` in place of urllib3's
    own, for the connections advocate does not validate.
    """

    def _new_conn(self):
        try:
            sock = _create_connection(
                (self._dns_host, self.port),
                self.timeout,
                self.connect_deadline,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except socket.gaierror as e:
            raise NameResolutionError(self.host, self, e) from e
        except TimeoutError as e:
            raise ConnectTimeoutError(
                self, f"Connection to {self.host} timed out."
            ) from e
        except OSError as e:
            raise NewConnectionError(
                self, f"Failed to establish a new connection: {e}"
            ) from e
        sys.audit("http.client.connect", self, self.host, self.port)
        return sock


class _WatchedHTTPConnection(
    _WatchedConnectionMixin, _DeadlineConnectMixin, HTTPConnection
):
    pass


class _WatchedHTTPSConnection(
    _WatchedConnectionMixin, _DeadlineConnectMixin, HTTPSConnection
):
    pass


# advocate's connections stay the base, so they keep validating every address.
class _WatchedValidatingHTTPConnection(
    _WatchedConnectionMixin, ValidatingHTTPConnection
):
    pass


class _WatchedValidatingHTTPSConnection(
    _WatchedConnectionMixin, ValidatingHTTPSConnection
):
    pass


class _WatchedHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = _WatchedHTTPConnection


class _WatchedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _WatchedHTTPSConnection


class _WatchedValidatingHTTPConnectionPool(ValidatingHTTPConnectionPool):
    ConnectionCls = _WatchedValidatingHTTPConnection


class _WatchedValidatingHTTPSConnectionPool(ValidatingHTTPSConnectionPool):
    ConnectionCls = _WatchedValidatingHTTPSConnection


class _DeadlineMixin:
    """
    Gives every hop of a request only the time left until one deadline.
    Requests passes the same `timeout` to every hop of a redirect chain, and
    applies it per socket operation: a single read or write may not take
    longer than that, but nothing stops a hop taking many of them, each
    getting the shrunken timeout again. Reading a status line and headers is
    exactly that, many small reads, so a server trickling them out a byte at a
    time could still hold a hop open long past the deadline. The watchdog
    hangs up whatever socket is open once the deadline passes; this checks the
    flag it leaves behind, because a hung-up connection can still hand back a
    response instead of raising.
    """

    request_deadline: _RequestDeadline
    operation_timeout: Optional[float] = None
    watched_pool_classes: dict

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for adapter in self.adapters.values():
            # An instance attribute, on both `PoolManager` and advocate's
            # `ValidatingPoolManager`: this leaves advocate's mount lock, which
            # only guards `session.mount()`, untouched.
            adapter.poolmanager.pool_classes_by_scheme = self.watched_pool_classes

    def send(self, request, **kwargs):
        remaining = self.request_deadline.deadline - time.monotonic()
        if remaining <= 0:
            raise request_exceptions.Timeout("The request did not finish in time.")
        # `resolve_redirects` calls `send` again for every hop, so each one
        # gets what is left rather than the whole budget. No single socket
        # operation waits longer than `operation_timeout`, however much of
        # the budget is left, so waiting for the answer cannot use up the
        # time the body was given.
        timeout = remaining
        if self.operation_timeout is not None:
            timeout = min(timeout, self.operation_timeout)
        kwargs["timeout"] = timeout
        try:
            response = super().send(request, **kwargs)
        except request_exceptions.ConnectionError as e:
            # A socket the watchdog hangs up mid-read can come back as this
            # instead of as a response with the flag below to check.
            if self.request_deadline.hung_up:
                raise request_exceptions.Timeout(
                    "The request did not finish in time."
                ) from e
            raise
        if self.request_deadline.hung_up:
            response.close()
            raise request_exceptions.Timeout("The request did not finish in time.")
        return response


class _WatchedProxyHTTPAdapter(HTTPAdapter):
    """
    Requests' adapter, except that a proxy's connection pools are watched the
    same as direct ones. Requests keeps a pool manager per proxy apart from
    `poolmanager`, so the pool classes put on that do not reach it.
    """

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        manager = super().proxy_manager_for(proxy, **proxy_kwargs)
        manager.pool_classes_by_scheme = self.poolmanager.pool_classes_by_scheme
        return manager


class _WatchedProxySession(requests.Session):
    def __init__(self):
        super().__init__()
        # Mounted before `_DeadlineMixin` puts the watched pool classes on
        # every adapter, which this one then hands on to its proxies. advocate
        # needs none of this: it refuses to send through a proxy at all.
        self.mount("https://", _WatchedProxyHTTPAdapter())
        self.mount("http://", _WatchedProxyHTTPAdapter())


class _DeadlineSession(_DeadlineMixin, _WatchedProxySession):
    watched_pool_classes = {
        "http": _WatchedHTTPConnectionPool,
        "https": _WatchedHTTPSConnectionPool,
    }


class _DeadlineAdvocateSession(_DeadlineMixin, advocate.Session):
    # Only `send` and the pool classes are changed, so advocate's validating
    # adapter still checks the address of every hop, redirects included.
    watched_pool_classes = {
        "http": _WatchedValidatingHTTPConnectionPool,
        "https": _WatchedValidatingHTTPSConnectionPool,
    }


def send_http_request(
    method: str,
    url: str,
    deadline: float,
    operation_timeout: Optional[float] = None,
    **kwargs,
) -> requests.Response:
    """
    Sends a request and reads its body, both over by `deadline`, redirects
    included, and returns the final response with its body in.

    :param method: The HTTP method.
    :param url: Where to send it.
    :param deadline: The `time.monotonic()` value the request must be over by.
    :param operation_timeout: The longest a single connect or read may wait,
        when that is shorter than what is left until `deadline`.
    :param kwargs: Anything else `requests.Session.request` accepts, except
        `timeout`, `stream` and `hooks`, which this function sets itself and
        must not be passed in.
    :return: The final response, its body already read.
    :raises requests.exceptions.Timeout: When the deadline passes.
    :raises requests.exceptions.TooManyRedirects: Past `MAX_REDIRECTS`.
    :raises UnacceptableAddressException: When a hop resolves to an address
        this installation does not allow.
    :raises ResponseTooLargeDispatchException: When a body, the final one or a
        redirect's, is larger than this installation accepts.
    """

    session_class = (
        _DeadlineSession
        if settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS is True
        else _DeadlineAdvocateSession
    )
    request_deadline = _RequestDeadline(deadline)

    def read_redirect_body(response, *args, **hook_kwargs):
        # Requests reads a redirect's body itself before following it, with no
        # deadline and no size ceiling. Hooks run first, so reading it here
        # puts it under both.
        if response.is_redirect:
            _read_body(response, request_deadline)

    _watchdog.watch(request_deadline)
    token = _current_request_deadline.set(request_deadline)
    try:
        # Closed on return, the same as `requests.request` does: that only
        # drops the idle connections in the pool, not the one the response is
        # streaming from.
        with session_class() as session:
            session.request_deadline = request_deadline
            session.operation_timeout = operation_timeout
            session.max_redirects = MAX_REDIRECTS
            response = session.request(
                method=method,
                url=url,
                stream=True,
                hooks={"response": [read_redirect_body]},
                **kwargs,
            )
        # A redirect that ends up the final response was already read by the
        # hook; reading again would find the socket empty.
        if not response._content_consumed:
            _read_body(response, request_deadline)
    finally:
        _current_request_deadline.reset(token)
        request_deadline.finish()

    return response
