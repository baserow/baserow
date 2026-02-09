import re
from ipaddress import ip_network
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import override_settings

import httpretty as httpretty
import pytest

from baserow.contrib.database.webhooks.validators import url_validator
from baserow.test_utils.helpers import stub_getaddrinfo

URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS = re.compile(r"(?!(www\.)?google\.com).*")


@httpretty.activate(verbose=True, allow_net_connect=False)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_blocks_internal_address(mock):
    httpretty.register_uri(httpretty.GET, "https://1.1.1.1/", status=200)
    httpretty.register_uri(httpretty.GET, "https://2.2.2.2/", status=200)
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200)

    # This request should go through
    url_validator("https://1.1.1.1/")

    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")


@httpretty.activate(verbose=True, allow_net_connect=False)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_blocks_invalid_urls(mock):
    httpretty.register_uri(httpretty.GET, "https://1.1.1.1/", status=200)
    httpretty.register_uri(httpretty.GET, "https://2.2.2.2/", status=200)
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200)

    # This request should go through
    url_validator("https://1.1.1.1/")

    # This request should not go through
    with pytest.raises(ValidationError) as exec_info:
        url_validator("google.com")
    assert exec_info.value.code == "invalid_url"
    with pytest.raises(ValidationError) as exec_info:
        url_validator("127.0.0.1")
    assert exec_info.value.code == "invalid_url"


@httpretty.activate(verbose=True, allow_net_connect=False)
@override_settings(BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("127.0.0.1/32")])
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_whitelist_rules(mock):
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200)
    httpretty.register_uri(httpretty.GET, "http://10.0.0.1/", status=200)

    # This request should go through
    url_validator("http://127.0.0.1/")

    # Other private addresses should still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://10.0.0.1/")
    assert exec_info.value.code == "invalid_url"


@httpretty.activate(verbose=True, allow_net_connect=False)
@override_settings(BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.1.1.1/32")])
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_blacklist_rules(mock):
    httpretty.register_uri(httpretty.GET, "https://1.1.1.1", status=200)
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200)
    httpretty.register_uri(httpretty.GET, "https://2.2.2.2/", status=200)

    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://1.1.1.1/")
    assert exec_info.value.code == "invalid_url"

    # Private address is still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("https://2.2.2.2/")


@httpretty.activate(verbose=True, allow_net_connect=False)
@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[re.compile(r"(?:www\.?)?google.com")]
)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_hostname_blacklist_rules(patched_addr_info):
    httpretty.register_uri(httpretty.GET, "https://google.com", status=200)
    httpretty.register_uri(httpretty.GET, "http://1.1.1.1", status=200)

    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://www.google.com/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("https://www.otherdomain.com")


@httpretty.activate(verbose=True, allow_net_connect=False)
@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS]
)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_hostname_blacklist_rules_only_allow_one_host(patched_addr_info):
    httpretty.register_uri(httpretty.GET, "https://google.com", status=200)
    httpretty.register_uri(httpretty.GET, "http://google.com", status=200)
    httpretty.register_uri(httpretty.GET, "http://1.1.1.1", status=200)
    httpretty.register_uri(httpretty.GET, "https://1.1.1.1", status=200)

    url_validator("https://www.google.com/")
    url_validator("https://google.com/")

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://www.otherdomain.com")
    assert exec_info.value.code == "invalid_url"

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://google2.com")
    assert exec_info.value.code == "invalid_url"


@httpretty.activate(verbose=True, allow_net_connect=False)
@override_settings(
    BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.0.0.0/8")],
    BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("1.1.1.1/32")],
)
def test_ssrf_combination_of_whitelist_blacklist_rules():
    httpretty.register_uri(httpretty.GET, "https://1.1.1.1", status=200)
    httpretty.register_uri(httpretty.GET, "https://1.1.1.2", status=200)
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200)
    httpretty.register_uri(httpretty.GET, "https://2.2.2.2/", status=200)

    url_validator("https://1.1.1.1/")

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://1.1.1.2/")
    assert exec_info.value.code == "invalid_url"

    # Private address is still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("https://2.2.2.2/")


@httpretty.activate(verbose=True, allow_net_connect=False)
@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS],
    BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.0.0.0/8")],
    BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("1.1.1.1/32")],
)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_ssrf_hostname_blacklist_overrides_ip_lists(
    mock,
):
    httpretty.register_uri(httpretty.GET, "https://1.1.1.1", status=200)
    httpretty.register_uri(httpretty.GET, "https://1.1.1.2", status=200)
    httpretty.register_uri(httpretty.GET, "http://127.0.0.1/", status=200)
    httpretty.register_uri(httpretty.GET, "https://2.2.2.2/", status=200)

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://1.1.1.1/")
    assert exec_info.value.code == "invalid_url"

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://1.1.1.2/")
    assert exec_info.value.code == "invalid_url"

    # Private address is still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("https://www.google.com/")
