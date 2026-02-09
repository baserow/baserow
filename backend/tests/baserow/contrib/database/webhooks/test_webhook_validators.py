import re
from ipaddress import ip_network
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import override_settings

import pytest
import responses

from baserow.contrib.database.webhooks.validators import url_validator
from baserow.test_utils.helpers import stub_getaddrinfo

URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS = re.compile(r"(?!(www\.)?google\.com).*")


@responses.activate
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_advocate_blocks_internal_address(mock):
    responses.add(responses.GET, "https://1.1.1.1/", status=200)
    responses.add(responses.GET, "https://2.2.2.2/", status=200)
    responses.add(responses.GET, "http://127.0.0.1/", status=200)

    # This request should go through
    url_validator("https://1.1.1.1/")

    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")


@responses.activate
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_advocate_blocks_invalid_urls(mock):
    responses.add(responses.GET, "https://1.1.1.1/", status=200)
    responses.add(responses.GET, "https://2.2.2.2/", status=200)
    responses.add(responses.GET, "http://127.0.0.1/", status=200)

    # This request should go through
    url_validator("https://1.1.1.1/")

    # This request should not go through
    with pytest.raises(ValidationError) as exec_info:
        url_validator("google.com")
    assert exec_info.value.code == "invalid_url"
    with pytest.raises(ValidationError) as exec_info:
        url_validator("127.0.0.1")
    assert exec_info.value.code == "invalid_url"


@responses.activate
@override_settings(BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("127.0.0.1/32")])
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_advocate_whitelist_rules(mock):
    responses.add(responses.GET, "http://127.0.0.1/", status=200)
    responses.add(responses.GET, "http://10.0.0.1/", status=200)

    # This request should go through
    url_validator("http://127.0.0.1/")

    # Other private addresses should still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://10.0.0.1/")
    assert exec_info.value.code == "invalid_url"


@responses.activate
@override_settings(BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.1.1.1/32")])
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_advocate_blacklist_rules(mock):
    responses.add(responses.GET, "https://1.1.1.1", status=200)
    responses.add(responses.GET, "http://127.0.0.1/", status=200)
    responses.add(responses.GET, "https://2.2.2.2/", status=200)

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


@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[re.compile(r"(?:www\.?)?google.com")]
)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_hostname_blacklist_rules(patched_addr_info):
    responses.add(responses.GET, "https://google.com", status=200)
    responses.add(responses.GET, "http://1.1.1.1", status=200)

    # The responses stub implemenation of socket.getaddrinfo is incorrect and doesn't
    # return an IP causing advocate to fail, instead we patch to fix this.

    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://www.google.com/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("https://www.otherdomain.com")


@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS]
)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_hostname_blacklist_rules_only_allow_one_host(patched_addr_info):
    responses.add(responses.GET, "https://google.com", status=200)
    responses.add(responses.GET, "http://google.com", status=200)
    responses.add(responses.GET, "http://1.1.1.1", status=200)
    responses.add(responses.GET, "https://1.1.1.1", status=200)

    url_validator("https://www.google.com/")
    url_validator("https://google.com/")

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://www.otherdomain.com")
    assert exec_info.value.code == "invalid_url"

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://google2.com")
    assert exec_info.value.code == "invalid_url"


@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.0.0.0/8")],
    BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("1.1.1.1/32")],
)
def test_advocate_combination_of_whitelist_blacklist_rules():
    responses.add(responses.GET, "https://1.1.1.1", status=200)
    responses.add(responses.GET, "https://1.1.1.2", status=200)
    responses.add(responses.GET, "http://127.0.0.1/", status=200)
    responses.add(responses.GET, "https://2.2.2.2/", status=200)

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


@responses.activate
@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS],
    BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.0.0.0/8")],
    BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("1.1.1.1/32")],
)
@patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
def test_advocate_hostname_blacklist_overrides_ip_lists(
    mock,
):
    responses.add(responses.GET, "https://1.1.1.1", status=200)
    responses.add(responses.GET, "https://1.1.1.2", status=200)
    responses.add(responses.GET, "http://127.0.0.1/", status=200)
    responses.add(responses.GET, "https://2.2.2.2/", status=200)

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
