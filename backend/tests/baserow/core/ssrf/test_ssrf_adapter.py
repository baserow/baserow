from unittest.mock import patch

import httpretty
import pytest

from baserow.core.ssrf import ssrf_safe_request, validate_url
from baserow.core.ssrf.exceptions import InvalidSSRFAddress
from baserow.core.ssrf.validator import SSRFValidator
from baserow.test_utils.helpers import stub_getaddrinfo


@httpretty.activate(verbose=True, allow_net_connect=False)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_safe_request_public_ip_allowed(mock_getaddrinfo):
    httpretty.register_uri(httpretty.GET, "http://1.1.1.1/", status=200, body="ok")
    response = ssrf_safe_request.get("http://1.1.1.1/", timeout=5)
    assert response.status_code == 200


@httpretty.activate(verbose=True, allow_net_connect=False)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_safe_request_private_ip_blocked(mock_getaddrinfo):
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200, body="ok")
    with pytest.raises(InvalidSSRFAddress):
        ssrf_safe_request.get("http://127.0.0.1/", timeout=5)


@httpretty.activate(verbose=True, allow_net_connect=False)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_safe_request_with_custom_validator(mock_getaddrinfo):
    from ipaddress import ip_network

    httpretty.register_uri(httpretty.GET, "http://1.1.1.1/", status=200, body="ok")

    # Blacklist 1.1.1.1
    validator = SSRFValidator(ip_blacklist=[ip_network("1.1.1.1/32")])
    with pytest.raises(InvalidSSRFAddress):
        ssrf_safe_request.get("http://1.1.1.1/", validator=validator, timeout=5)


@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_validate_url_public_ip(mock_getaddrinfo):
    ip, port = validate_url("1.1.1.1", 443)
    assert ip == "1.1.1.1"
    assert port == 443


@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_validate_url_private_ip_blocked(mock_getaddrinfo):
    with pytest.raises(InvalidSSRFAddress):
        validate_url("127.0.0.1", 80)


@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_validate_url_with_validator(mock_getaddrinfo):
    from ipaddress import ip_network

    validator = SSRFValidator(ip_whitelist=[ip_network("127.0.0.1/32")])
    ip, port = validate_url("127.0.0.1", 80, validator=validator)
    assert ip == "127.0.0.1"
