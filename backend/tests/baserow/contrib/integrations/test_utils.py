import gzip
import ipaddress
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest
import requests
from requests import exceptions as request_exceptions

import advocate
from advocate import AddrValidator
from advocate.connection import UnacceptableAddressException
from baserow.contrib.integrations.utils import (
    MAX_REDIRECTS,
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


def stall(length=10, seconds=3.0):
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


def test_a_body_that_trickles_is_hung_up_on_at_the_deadline(settings):
    """
    urllib3 waits for a whole 64 KB chunk before `iter_content` returns one, so
    a server sending a byte at a time kept the deadline check from ever running:
    this body took the full 10 seconds.
    """

    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    with local_server({"/": trickle(length=100)}) as (base, _):
        response = requests.get(base + "/", stream=True, timeout=5)
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            read_response_within_limit(response, 1)
        elapsed = time.monotonic() - started

    assert elapsed < 2


def test_a_body_that_stops_arriving_is_reported_as_a_timeout(settings):
    """
    Reading `raw` directly skips the wrapping `iter_content` does, so a read
    timeout has to come out as the `Timeout` the service answers with a 504, not
    as urllib3's own error or a `ConnectionError`.
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


def test_a_chunked_body_is_read_whole(settings):
    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024 * 1024
    with local_server({"/": chunked([b'{"a": ', b"1}"])}) as (base, _):
        response = requests.get(base + "/", stream=True, timeout=5)
        read_response_within_limit(response, 5)

    assert response.json() == {"a": 1}


def test_a_redirect_chain_is_given_up_on_at_the_deadline(settings):
    """
    Requests gives every hop a fresh timeout, so six hops that each answer in
    0.6 seconds would take 3.6 seconds against a 1 second budget.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {f"/{i}": redirect(f"/{i + 1}", delay=0.6) for i in range(6)}
    routes["/6"] = answer()
    with local_server(routes) as (base, _):
        started = time.monotonic()
        with pytest.raises(request_exceptions.Timeout):
            send_http_request("GET", base + "/0", deadline=started + 1)
        elapsed = time.monotonic() - started

    assert elapsed < 2


def test_a_redirect_whose_body_trickles_is_given_up_on(settings):
    """
    Requests reads a redirect's body itself before following it, outside any
    deadline, so this one alone would hold the request for 10 seconds.
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

    assert elapsed < 2
    assert ("GET", "/done") not in seen


def test_a_redirect_chain_stops_at_the_cap(settings):
    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = True
    routes = {f"/{i}": redirect(f"/{i + 1}") for i in range(MAX_REDIRECTS + 2)}
    routes[f"/{MAX_REDIRECTS + 2}"] = answer()
    with local_server(routes) as (base, seen):
        with pytest.raises(request_exceptions.TooManyRedirects):
            send_http_request("GET", base + "/0", deadline=time.monotonic() + 5)

    assert len(seen) <= MAX_REDIRECTS + 1


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


def test_every_hop_is_checked_against_the_address_rules(settings):
    """
    The first address is allowed and the one it redirects to is not. Only the
    port differs, which is enough for the validator to tell them apart.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = False
    with local_server({"/done": answer()}) as (other, other_seen):
        routes = {"/start": redirect(other + "/done")}
        with local_server(routes) as (base, _):
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

    assert other_seen == []
