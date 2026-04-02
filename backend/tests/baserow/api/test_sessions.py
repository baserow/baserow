import pytest

from baserow.api.sessions import validate_ip_address


@pytest.mark.parametrize(
    "value,expected",
    [
        # Valid IPv4
        ("192.168.1.1", "192.168.1.1"),
        ("10.0.0.1", "10.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("0.0.0.0", "0.0.0.0"),  # noqa: S104
        ("255.255.255.255", "255.255.255.255"),
        # Valid IPv6
        ("::1", "::1"),
        ("2001:db8::1", "2001:db8::1"),
        ("fe80::1", "fe80::1"),
        # IPv6 normalization
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
        # Invalid values
        (None, None),
        ("", None),
        ("unknown", None),
        ("1.2.3.4:1234", None),
        ("not_an_ip", None),
        ("999.999.999.999", None),
        ("1.2.3", None),
        ("http://1.2.3.4", None),
        ("1.2.3.4/24", None),
    ],
)
def test_validate_ip_address(value, expected):
    assert validate_ip_address(value) == expected
