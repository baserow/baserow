import re
from ipaddress import ip_network

from django.core.exceptions import ValidationError
from django.test import override_settings

import pytest

import advocate.connection as advocate_connection
from baserow.contrib.database.webhooks.validators import url_validator

URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS = re.compile(r"(?!(www\.)?google\.com).*")


class _DummySocket:
    def settimeout(self, *args, **kwargs):
        pass

    def connect(self, *args, **kwargs):
        # Never do real outbound network in unit tests.
        return None

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _disable_real_network(monkeypatch):
    monkeypatch.setattr(
        advocate_connection.socket, "socket", lambda *args, **kwargs: _DummySocket()
    )


def test_advocate_blocks_internal_address():
    # This request should go through
    url_validator("https://1.1.1.1/")

    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")


def test_advocate_blocks_invalid_urls():
    # This request should go through
    url_validator("https://1.1.1.1/")

    # This request should not go through
    with pytest.raises(ValidationError) as exec_info:
        url_validator("google.com")
    assert exec_info.value.code == "invalid_url"
    with pytest.raises(ValidationError) as exec_info:
        url_validator("127.0.0.1")
    assert exec_info.value.code == "invalid_url"


@override_settings(BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("127.0.0.1/32")])
def test_advocate_whitelist_rules():
    # This request should go through
    url_validator("http://127.0.0.1/")

    # Other private addresses should still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://10.0.0.1/")
    assert exec_info.value.code == "invalid_url"


@override_settings(BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.1.1.1/32")])
def test_advocate_blacklist_rules():
    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://1.1.1.1/")
    assert exec_info.value.code == "invalid_url"

    # Private address is still blocked
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("http://127.0.0.1/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("http://2.2.2.2/")


@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[re.compile(r"(?:www\.?)?google.com")]
)
def test_hostname_blacklist_rules():
    # This request should not go through
    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://www.google.com/")
    assert exec_info.value.code == "invalid_url"

    # This request should still go through
    url_validator("https://www.cloudflare.com")


@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS]
)
def test_hostname_blacklist_rules_only_allow_one_host():
    url_validator("https://www.google.com/")
    url_validator("https://google.com/")

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://www.otherdomain.com")
    assert exec_info.value.code == "invalid_url"

    with pytest.raises(ValidationError, match="Invalid URL") as exec_info:
        url_validator("https://google2.com")
    assert exec_info.value.code == "invalid_url"


@override_settings(
    BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.0.0.0/8")],
    BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("1.1.1.1/32")],
)
def test_advocate_combination_of_whitelist_blacklist_rules():
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


@override_settings(
    BASEROW_WEBHOOKS_URL_REGEX_BLACKLIST=[URL_BLACKLIST_ONLY_ALLOWING_GOOGLE_WEBHOOKS],
    BASEROW_WEBHOOKS_IP_BLACKLIST=[ip_network("1.0.0.0/8")],
    BASEROW_WEBHOOKS_IP_WHITELIST=[ip_network("1.1.1.1/32")],
)
def test_advocate_hostname_blacklist_overrides_ip_lists():
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
