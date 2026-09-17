import gc
import gzip
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
import weakref
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import pytest
import requests
import urllib3.util.connection
from loguru import logger
from requests import exceptions as request_exceptions
from urllib3.exceptions import SSLError

try:
    from compression import zstd
except ImportError:
    zstd = None

import advocate
from advocate import AddrValidator
from advocate.connection import UnacceptableAddressException
from baserow.contrib.integrations.utils import (
    DEADLINE_WATCHDOG_THREAD_NAME,
    MAX_REDIRECTS,
    _pending_deadlines,
    _RequestDeadline,
    _watchdog,
    read_response_within_limit,
    send_http_request,
)


class _QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # A client hanging up mid answer is what these tests provoke.
        pass


@contextmanager
def local_server(routes):
    """
    Serves `routes`, a dict of path to handler function, on a free port on
    127.0.0.1. Yields the base URL and the list of (method, path) it was asked
    for, in order.

    A real socket rather than a mock: how long a read blocks is decided inside
    urllib3, and a mock handing over tiny chunks hides exactly that.
    """

    seen = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _route(self):
            seen.append((self.command, self.path))
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            routes[self.path](self)

        do_GET = _route
        do_POST = _route

        def log_message(self, *args):
            pass

    server = _QuietServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", seen
    finally:
        server.shutdown()
        server.server_close()


def answer(body=b"{}", headers=None, status=200):
    def handle(handler):
        handler.send_response(status)
        for key, value in (headers or {}).items():
            handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    return handle


def redirect(to, delay=0.0, status=302):
    def handle(handler):
        time.sleep(delay)
        handler.send_response(status)
        handler.send_header("Location", to)
        handler.send_header("Content-Length", "0")
        handler.end_headers()

    return handle


def trickle(status=200, headers=None, length=100):
    """A byte every 0.1 seconds, so `length` bytes take `length / 10` seconds."""

    def handle(handler):
        handler.send_response(status)
        for key, value in (headers or {}).items():
            handler.send_header(key, value)
        handler.send_header("Content-Length", str(length))
        handler.end_headers()
        try:
            for _ in range(length):
                handler.wfile.write(b"x")
                handler.wfile.flush()
                time.sleep(0.1)
        except OSError:
            pass

    return handle


def stall(length=10, seconds=10.0):
    """Headers, then nothing at all."""

    def handle(handler):
        handler.send_response(200)
        handler.send_header("Content-Length", str(length))
        handler.end_headers()
        handler.wfile.flush()
        time.sleep(seconds)

    return handle


def chunked(parts):
    def handle(handler):
        handler.send_response(200)
        handler.send_header("Transfer-Encoding", "chunked")
        handler.end_headers()
        for part in parts:
            handler.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
        handler.wfile.write(b"0\r\n\r\n")

    return handle


def compressed_trickle(encoding, compress):
    """
    A compressed body with no length, so the client reads until the connection
    closes, sent a byte every 0.1 seconds and taking well over 10 seconds.
    """

    body = compress(json.dumps({"title": secrets.token_hex(1024)}).encode())

    def handle(handler):
        handler.send_response(200)
        handler.send_header("Content-Encoding", encoding)
        handler.send_header("Connection", "close")
        handler.end_headers()
        try:
            for byte in body:
                handler.wfile.write(bytes([byte]))
                handler.wfile.flush()
                time.sleep(0.1)
        except OSError:
            pass

    return handle


def header_trickle(length=50, delay=0.2):
    """
    A status line straight to the socket, then one header byte every `delay`
    seconds, so the headers alone take `length * delay` seconds to arrive and
    are never completed.
    """

    def handle(handler):
        handler.wfile.write(b"HTTP/1.1 200 OK\r\n")
        try:
            for _ in range(length):
                handler.wfile.write(b"x")
                handler.wfile.flush()
                time.sleep(delay)
        except OSError:
            pass

    return handle


@contextmanager
def unanswered_address():
    """
    Yields the host and port of a listener whose queue is full, so a connect to
    it waits out its whole timeout, the same as one to an address that drops
    packets.
    """

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(0)
    address = listener.getsockname()
    queued = []
    try:
        while True:
            client = socket.socket()
            queued.append(client)
            client.settimeout(0.1)
            try:
                client.connect(address)
            except TimeoutError:
                break
        yield address
    finally:
        for client in queued:
            client.close()
        listener.close()


def test_a_body_that_trickles_is_hung_up_on_at_the_deadline(settings):
    """
    A body sent a byte at a time is given up on at the deadline rather than
    once it is complete, ten seconds later.
    """

    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    with local_server({"/": trickle(length=100)}) as (base, _):
        response = requests.get(base + "/", stream=True, timeout=5)
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            read_response_within_limit(response, 1)
        elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_body_that_stops_arriving_is_reported_as_a_timeout(settings):
    """
    A read timeout comes out as the `Timeout` the service answers with a 504,
    not as urllib3's own error or a `ConnectionError`.
    """

    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    with local_server({"/": stall()}) as (base, _):
        response = requests.get(base + "/", stream=True, timeout=0.5)
        with pytest.raises(request_exceptions.Timeout):
            read_response_within_limit(response, 5)


def test_a_compressed_body_is_read_decoded(settings):
    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    body = json.dumps({"title": "x" * 5000}).encode()
    route = answer(gzip.compress(body), headers={"Content-Encoding": "gzip"})
    with local_server({"/": route}) as (base, _):
        response = requests.get(base + "/", stream=True, timeout=5)
        read_response_within_limit(response, 5)

    assert response.json() == {"title": "x" * 5000}


@pytest.mark.parametrize(
    "encoding,compress",
    [
        ("gzip", gzip.compress),
        pytest.param(
            "zstd",
            zstd.compress if zstd else None,
            marks=pytest.mark.skipif(zstd is None, reason="no zstd support"),
        ),
    ],
)
def test_a_compressed_body_cut_off_at_the_deadline_is_a_timeout(
    settings, encoding, compress
):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    with local_server({"/": compressed_trickle(encoding, compress)}) as (base, _):
        started = time.monotonic()
        deadline = started + 1
        with pytest.raises(request_exceptions.Timeout):
            response = send_http_request("GET", base + "/", deadline=deadline)
            read_response_within_limit(response, 1, deadline=deadline)
        elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_chunked_body_is_read_whole(settings):
    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    with local_server({"/": chunked([b'{"a": ', b"1}"])}) as (base, _):
        response = requests.get(base + "/", stream=True, timeout=5)
        read_response_within_limit(response, 5)

    assert response.json() == {"a": 1}


def test_a_broken_tls_read_is_reported_as_an_ssl_error():
    """
    A broken TLS read comes out as Requests' own `SSLError`, not as an unmapped
    urllib3 error.
    """

    response = requests.Response()
    response.raw = Mock()
    response.raw.read1.side_effect = SSLError("bad record mac")

    with pytest.raises(request_exceptions.SSLError):
        read_response_within_limit(response, 5)


def test_a_broken_tls_read_past_the_deadline_is_reported_as_a_timeout():
    response = requests.Response()
    response.raw = Mock()
    response.raw.read1.side_effect = SSLError("bad record mac")

    with pytest.raises(request_exceptions.Timeout):
        read_response_within_limit(response, 0, deadline=time.monotonic() - 1)


def test_a_redirect_chain_is_given_up_on_at_the_deadline(settings):
    """
    Every hop answers within the deadline, and the chain as a whole, more than
    ten seconds of hops, is still given up on once it goes past it.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    hops = MAX_REDIRECTS + 1
    routes = {f"/{i}": redirect(f"/{i + 1}", delay=0.95) for i in range(hops)}
    routes[f"/{hops}"] = answer()
    with local_server(routes) as (base, _):
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            send_http_request("GET", base + "/0", deadline=started + 1)
        elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_redirect_whose_body_trickles_is_given_up_on(settings):
    """
    A redirect's own body, ten seconds of it, is read under the same deadline
    before the redirect is followed.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    routes = {
        "/start": trickle(status=302, headers={"Location": "/done"}, length=100),
        "/done": answer(),
    }
    with local_server(routes) as (base, seen):
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            send_http_request("GET", base + "/start", deadline=started + 1)
        elapsed = time.monotonic() - started

    assert elapsed < 5
    assert ("GET", "/done") not in seen


def test_a_redirect_chain_stops_at_the_cap(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {f"/{i}": redirect(f"/{i + 1}") for i in range(MAX_REDIRECTS + 2)}
    routes[f"/{MAX_REDIRECTS + 2}"] = answer()
    with local_server(routes) as (base, seen):
        with pytest.raises(request_exceptions.TooManyRedirects):
            send_http_request("GET", base + "/0", deadline=time.monotonic() + 5)

    assert len(seen) == MAX_REDIRECTS + 1


def test_a_redirect_is_followed_the_way_requests_follows_it(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {"/start": redirect("/done"), "/done": answer(b'{"ok": true}')}
    with local_server(routes) as (base, seen):
        response = send_http_request(
            "POST", base + "/start", deadline=time.monotonic() + 5, data={"a": "b"}
        )
        read_response_within_limit(response, 5)

    assert response.json() == {"ok": True}
    # A 302 after a POST is followed with a GET, as Requests does.
    assert seen == [("POST", "/start"), ("GET", "/done")]


def test_a_redirect_with_no_location_to_follow_keeps_its_body(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    route = answer(b'{"moved": true}', headers={"Location": ""}, status=302)
    with local_server({"/": route}) as (base, _):
        deadline = time.monotonic() + 5
        response = send_http_request("GET", base + "/", deadline=deadline)
        read_response_within_limit(response, 5, deadline=deadline)

    assert response.status_code == 302
    assert response.json() == {"moved": True}


def test_a_redirect_that_is_not_followed_keeps_its_body(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {
        "/start": answer(b'{"moved": true}', headers={"Location": "/done"}, status=302),
        "/done": answer(),
    }
    with local_server(routes) as (base, seen):
        deadline = time.monotonic() + 5
        response = send_http_request(
            "GET", base + "/start", deadline=deadline, allow_redirects=False
        )
        read_response_within_limit(response, 5, deadline=deadline)

    assert response.status_code == 302
    assert response.json() == {"moved": True}
    assert seen == [("GET", "/start")]


def test_a_redirect_to_the_same_host_reuses_the_connection(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    ports = []

    def recording(route):
        def handle(handler):
            ports.append(handler.client_address[1])
            route(handler)

        return handle

    routes = {
        "/a": recording(
            answer(b'{"moved": true}', headers={"Location": "/b"}, status=302)
        ),
        "/b": recording(answer(b'{"ok": true}')),
    }
    with local_server(routes) as (base, seen):
        deadline = time.monotonic() + 5
        response = send_http_request("GET", base + "/a", deadline=deadline)
        read_response_within_limit(response, 5, deadline=deadline)

    assert seen == [("GET", "/a"), ("GET", "/b")]
    assert len(ports) == 2
    assert ports[0] == ports[1]


def test_a_read_response_is_freed_without_the_cycle_collector(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    with local_server({"/": answer(b'{"ok": true}')}) as (base, _):
        gc.collect()
        gc.disable()
        try:
            deadline = time.monotonic() + 5
            response = send_http_request("GET", base + "/", deadline=deadline)
            read_response_within_limit(response, 5, deadline=deadline)
            assert response.json() == {"ok": True}
            freed = weakref.ref(response)
            del response
            assert freed() is None
        finally:
            gc.enable()


def test_every_hop_is_checked_against_the_address_rules(settings):
    """
    The first address is allowed and the one it redirects to is not. Only the
    port differs, which is enough for the validator to tell them apart.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = False
    with local_server({"/done": answer()}) as (other, other_seen):
        routes = {"/start": redirect(other + "/done")}
        with local_server(routes) as (base, seen):
            validator = AddrValidator(
                ip_whitelist={ipaddress.ip_network("127.0.0.1/32")},
                port_whitelist={int(base.rsplit(":", 1)[1])},
                autodetect_local_addresses=False,
            )
            with patch.object(advocate.Session, "DEFAULT_VALIDATOR", validator):
                with pytest.raises(UnacceptableAddressException):
                    send_http_request(
                        "GET", base + "/start", deadline=time.monotonic() + 5
                    )

    assert seen == [("GET", "/start")]
    assert other_seen == []


def test_a_response_whose_headers_trickle_is_given_up_on_at_the_deadline(settings):
    """
    Headers sent a byte at a time never leave a single read waiting long enough
    to time out, and the request is still hung up on at the deadline.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    with local_server({"/": header_trickle()}) as (base, _):
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            send_http_request("GET", base + "/", deadline=started + 1)
        elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_redirect_to_trickling_headers_is_given_up_on_at_the_deadline(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {"/start": redirect("/slow"), "/slow": header_trickle()}
    with local_server(routes) as (base, _):
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            send_http_request("GET", base + "/start", deadline=started + 1)
        elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_redirect_to_another_host_whose_headers_trickle_is_given_up_on(settings):
    """
    The second hop opens a connection of its own rather than reusing the
    first, and the watchdog still hangs it up.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    with local_server({"/slow": header_trickle()}) as (other, _):
        with local_server({"/start": redirect(other + "/slow")}) as (base, _):
            started = time.monotonic()
            with pytest.raises(request_exceptions.Timeout):
                send_http_request("GET", base + "/start", deadline=started + 1)
            elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_hang_up_that_raises_does_not_stop_the_watchdog(settings):
    """
    One watched request's hang-up blowing up must not take the single
    watchdog thread down with it: a second request past its own deadline is
    still hung up on, rather than left open for as long as the server likes.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    # Handed to the watchdog directly rather than sent, so no request has to
    # finish before this deadline passes on a busy runner.
    broken = _RequestDeadline(time.monotonic())
    failed = threading.Event()

    def hang_up():
        failed.set()
        raise Exception("boom")

    broken.hang_up = hang_up
    _watchdog.watch(broken)
    assert failed.wait(5)

    with local_server({"/slow": header_trickle()}) as (base, _):
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            send_http_request("GET", base + "/slow", deadline=started + 1)
        elapsed = time.monotonic() - started

    assert elapsed < 5


def test_a_failed_hang_up_does_not_log_the_address(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True

    class FailingClose(socket.socket):
        # Named like a real socket, so its repr is as short as one: loguru
        # cuts a long repr off before the address it would otherwise show.
        __module__ = "socket"
        __qualname__ = "socket"

        def shutdown(self, how):
            # Left connected: on Linux a shut down socket still names its
            # peer, which macOS forgets as soon as it is shut down.
            pass

        def close(self):
            raise OSError("boom")

    written = []
    sink_id = logger.add(written.append, level="DEBUG", diagnose=True, backtrace=True)
    try:
        with local_server({}) as (base, _):
            host, port = base.removeprefix("http://").split(":")
            connected = socket.create_connection((host, int(port)))
            failing = FailingClose(fileno=os.dup(connected.fileno()))
            request_deadline = _RequestDeadline(time.monotonic())
            request_deadline._sockets.append(failing)
            _watchdog.watch(request_deadline)
            for _ in range(50):
                if written:
                    break
                time.sleep(0.1)

            socket.socket.close(failing)
            connected.close()
    finally:
        logger.remove(sink_id)

    logged = "".join(written)
    assert "OSError" in logged
    assert "raddr" not in logged
    assert port not in logged


def test_the_watchdog_does_not_outlive_a_finished_request(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    with local_server({"/": answer()}) as (base, _):
        deadlines = []
        for _ in range(2):
            deadline = time.monotonic() + 5
            response = send_http_request("GET", base + "/", deadline=deadline)
            assert deadline in _pending_deadlines()
            read_response_within_limit(response, 5, deadline=deadline)
            deadlines.append(deadline)

    assert not set(deadlines) & set(_pending_deadlines())
    watchdogs = [
        thread
        for thread in threading.enumerate()
        if thread.name == DEADLINE_WATCHDOG_THREAD_NAME
    ]
    assert len(watchdogs) == 1


@pytest.mark.parametrize("allow_private_address", [True, False])
def test_every_address_of_a_host_shares_the_deadline(settings, allow_private_address):
    """
    A host with several addresses is tried one after another, and the address
    lookup hands every attempt the timeout the hop started with. Four addresses
    that never answer would take four of those. Both with and without
    advocate, which has an address loop of its own.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = allow_private_address
    with unanswered_address() as (host, port):
        records = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        validator = AddrValidator(
            ip_whitelist={ipaddress.ip_network("127.0.0.1/32")},
            port_whitelist={port},
            autodetect_local_addresses=False,
        )
        with (
            patch("socket.getaddrinfo", return_value=records * 4),
            patch.object(advocate.Session, "DEFAULT_VALIDATOR", validator),
        ):
            started = time.monotonic()
            with pytest.raises(request_exceptions.Timeout):
                send_http_request(
                    "GET", f"http://unanswered.example:{port}/", deadline=started + 1
                )
            elapsed = time.monotonic() - started

    assert elapsed < 2.5


def test_a_connection_that_opens_after_the_deadline_is_hung_up_on(settings):
    """
    Standing in for a slow DNS lookup or a slow handshake: the deadline passes
    while the connection is still being made, so the watchdog's one pass over
    already-open connections never saw it. The connection itself has to catch
    up once it finishes connecting, or the header trickle below would hold the
    request open indefinitely.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    real_create_connection = urllib3.util.connection.create_connection

    def slow_create_connection(*args, **kwargs):
        time.sleep(1.2)
        return real_create_connection(*args, **kwargs)

    with local_server({"/": header_trickle()}) as (base, _):
        with patch(
            "urllib3.util.connection.create_connection",
            side_effect=slow_create_connection,
        ):
            started = time.monotonic()
            with pytest.raises(request_exceptions.Timeout):
                send_http_request("GET", base + "/", deadline=started + 1)
            elapsed = time.monotonic() - started

    assert elapsed < 5


def test_the_watchdog_is_cancelled_when_the_request_raises(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {f"/{i}": redirect(f"/{i + 1}") for i in range(MAX_REDIRECTS + 2)}
    routes[f"/{MAX_REDIRECTS + 2}"] = answer()
    with local_server(routes) as (base, _):
        deadline = time.monotonic() + 5
        with pytest.raises(request_exceptions.TooManyRedirects):
            send_http_request("GET", base + "/0", deadline=deadline)

    assert deadline not in _pending_deadlines()
