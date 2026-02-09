import re
from ipaddress import ip_address, ip_network
from unittest.mock import patch

import pytest

from baserow.core.ssrf.exceptions import InvalidSSRFAddress
from baserow.core.ssrf.validator import SSRFValidator
from baserow.test_utils.helpers import stub_getaddrinfo


class TestIsIpAllowed:
    """Tests for SSRFValidator.is_ip_allowed()."""

    def setup_method(self):
        self.validator = SSRFValidator()

    # -- Public IPs should be allowed --

    def test_public_ipv4_allowed(self):
        assert self.validator.is_ip_allowed(ip_address("1.1.1.1")) is True
        assert self.validator.is_ip_allowed(ip_address("8.8.8.8")) is True
        assert self.validator.is_ip_allowed(ip_address("93.184.216.34")) is True

    def test_public_ipv6_allowed(self):
        assert self.validator.is_ip_allowed(ip_address("2606:4700::1111")) is True

    # -- Private RFC1918 addresses should be blocked --

    def test_loopback_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("127.0.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("127.0.0.2")) is False
        assert self.validator.is_ip_allowed(ip_address("::1")) is False

    def test_rfc1918_10_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("10.0.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("10.255.255.255")) is False

    def test_rfc1918_172_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("172.16.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("172.31.255.255")) is False

    def test_rfc1918_192_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("192.168.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("192.168.255.255")) is False

    # -- Special ranges should be blocked --

    def test_link_local_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("169.254.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("169.254.169.254")) is False

    def test_cgnat_blocked(self):
        """CGNAT (100.64.0.0/10) is not is_private but is not is_global."""
        assert self.validator.is_ip_allowed(ip_address("100.64.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("100.127.255.255")) is False

    def test_unspecified_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("0.0.0.0")) is False  # noqa S104

    def test_broadcast_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("255.255.255.255")) is False

    def test_documentation_ranges_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("192.0.2.1")) is False
        assert self.validator.is_ip_allowed(ip_address("198.51.100.1")) is False
        assert self.validator.is_ip_allowed(ip_address("203.0.113.1")) is False

    def test_6to4_relay_blocked(self):
        """192.88.99.0/24 (6to4 relay) is not is_global."""
        assert self.validator.is_ip_allowed(ip_address("192.88.99.1")) is False

    # -- IPv4-mapped IPv6 unwrapping --

    def test_ipv4_mapped_ipv6_private_blocked(self):
        assert self.validator.is_ip_allowed(ip_address("::ffff:127.0.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("::ffff:10.0.0.1")) is False
        assert self.validator.is_ip_allowed(ip_address("::ffff:192.168.1.1")) is False

    def test_ipv4_mapped_ipv6_public_allowed(self):
        assert self.validator.is_ip_allowed(ip_address("::ffff:1.1.1.1")) is True
        assert self.validator.is_ip_allowed(ip_address("::ffff:8.8.8.8")) is True

    # -- Custom whitelist --

    def test_whitelist_overrides_private(self):
        validator = SSRFValidator(ip_whitelist=[ip_network("127.0.0.1/32")])
        assert validator.is_ip_allowed(ip_address("127.0.0.1")) is True
        # Other private addresses still blocked
        assert validator.is_ip_allowed(ip_address("10.0.0.1")) is False

    def test_whitelist_overrides_blacklist(self):
        validator = SSRFValidator(
            ip_blacklist=[ip_network("1.0.0.0/8")],
            ip_whitelist=[ip_network("1.1.1.1/32")],
        )
        assert validator.is_ip_allowed(ip_address("1.1.1.1")) is True
        assert validator.is_ip_allowed(ip_address("1.1.1.2")) is False

    # -- Custom blacklist --

    def test_blacklist_blocks_public_ip(self):
        validator = SSRFValidator(ip_blacklist=[ip_network("1.1.1.1/32")])
        assert validator.is_ip_allowed(ip_address("1.1.1.1")) is False
        assert validator.is_ip_allowed(ip_address("8.8.8.8")) is True

    def test_blacklist_cidr_range(self):
        validator = SSRFValidator(ip_blacklist=[ip_network("1.0.0.0/8")])
        assert validator.is_ip_allowed(ip_address("1.1.1.1")) is False
        assert validator.is_ip_allowed(ip_address("1.255.255.255")) is False
        assert validator.is_ip_allowed(ip_address("2.0.0.1")) is True


class TestIsHostnameAllowed:
    """Tests for SSRFValidator.is_hostname_allowed()."""

    def test_no_blacklist_allows_all(self):
        validator = SSRFValidator()
        assert validator.is_hostname_allowed("example.com") is True
        assert validator.is_hostname_allowed("google.com") is True

    def test_hostname_blacklist_blocks_match(self):
        validator = SSRFValidator(
            hostname_blacklist=[re.compile(r"(?:www\.?)?google\.com")]
        )
        assert validator.is_hostname_allowed("google.com") is False
        assert validator.is_hostname_allowed("www.google.com") is False
        assert validator.is_hostname_allowed("otherdomain.com") is True

    def test_hostname_blacklist_only_allow_one_host(self):
        """A regex that blocks everything except google.com."""
        validator = SSRFValidator(
            hostname_blacklist=[re.compile(r"(?!(www\.)?google\.com).*")]
        )
        assert validator.is_hostname_allowed("google.com") is True
        assert validator.is_hostname_allowed("www.google.com") is True
        assert validator.is_hostname_allowed("otherdomain.com") is False
        assert validator.is_hostname_allowed("google2.com") is False

    def test_hostname_with_trailing_dot(self):
        validator = SSRFValidator(hostname_blacklist=[re.compile(r"evil\.com")])
        assert validator.is_hostname_allowed("evil.com.") is False
        assert validator.is_hostname_allowed("evil.com") is False


class TestValidateAddress:
    """Tests for SSRFValidator.validate_address()."""

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_public_ip_allowed(self, mock_getaddrinfo):
        validator = SSRFValidator()
        ip, port = validator.validate_address("1.1.1.1", 443)
        assert ip == "1.1.1.1"
        assert port == 443

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_private_ip_blocked(self, mock_getaddrinfo):
        validator = SSRFValidator()
        with pytest.raises(InvalidSSRFAddress):
            validator.validate_address("127.0.0.1", 80)

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_hostname_resolving_to_public_allowed(self, mock_getaddrinfo):
        validator = SSRFValidator()
        ip, port = validator.validate_address("example.com", 443)
        # stub_getaddrinfo resolves hostnames to 1.1.1.1
        assert ip == "1.1.1.1"

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_hostname_blacklist_blocks_before_resolution(self, mock_getaddrinfo):
        validator = SSRFValidator(hostname_blacklist=[re.compile(r"evil\.com")])
        with pytest.raises(InvalidSSRFAddress, match="blocked by blacklist"):
            validator.validate_address("evil.com", 443)

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_whitelist_allows_private_ip(self, mock_getaddrinfo):
        validator = SSRFValidator(ip_whitelist=[ip_network("127.0.0.1/32")])
        ip, port = validator.validate_address("127.0.0.1", 80)
        assert ip == "127.0.0.1"

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_blacklist_blocks_public_ip(self, mock_getaddrinfo):
        validator = SSRFValidator(ip_blacklist=[ip_network("1.1.1.1/32")])
        with pytest.raises(InvalidSSRFAddress):
            validator.validate_address("1.1.1.1", 443)

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_combined_rules(self, mock_getaddrinfo):
        """Whitelist overrides blacklist, but blacklisted IPs not in whitelist
        are still blocked."""
        validator = SSRFValidator(
            ip_blacklist=[ip_network("1.0.0.0/8")],
            ip_whitelist=[ip_network("1.1.1.1/32")],
        )
        ip, port = validator.validate_address("1.1.1.1", 443)
        assert ip == "1.1.1.1"

        with pytest.raises(InvalidSSRFAddress):
            validator.validate_address("1.1.1.2", 443)

    @patch("socket.getaddrinfo", wraps=stub_getaddrinfo)
    def test_hostname_blacklist_overrides_ip_lists(self, mock_getaddrinfo):
        """Hostname blacklist is checked first before IP resolution."""
        validator = SSRFValidator(
            hostname_blacklist=[re.compile(r"(?!(www\.)?google\.com).*")],
            ip_blacklist=[ip_network("1.0.0.0/8")],
            ip_whitelist=[ip_network("1.1.1.1/32")],
        )
        # IP 1.1.1.1 is whitelisted, but hostname "1.1.1.1" is blocked by
        # the hostname regex that only allows google.com
        with pytest.raises(InvalidSSRFAddress, match="blocked by blacklist"):
            validator.validate_address("1.1.1.1", 443)

        # google.com passes hostname check, resolves to 1.1.1.1 (via stub),
        # which is in the whitelist
        ip, port = validator.validate_address("www.google.com", 443)
        assert ip == "1.1.1.1"
