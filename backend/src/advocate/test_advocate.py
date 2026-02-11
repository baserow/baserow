# ruff: noqa
from __future__ import division

import socket

import pytest

# This needs to be done before third-party imports to make sure they all use
# our wrapped socket class, especially in case of subclasses.
from .monkeypatching import CheckedSocket, DisallowedConnectException

import ipaddress
import pickle
import unittest
from unittest.mock import patch

import responses

import advocate
from advocate import AddrValidator
from advocate.addrvalidator import canonicalize_hostname
from advocate.api import RequestsAPIWrapper
from advocate.connection import advocate_getaddrinfo
from advocate.exceptions import (
    ConfigException,
    MountDisabledException,
    NameserverException,
    UnacceptableAddressException,
)
from advocate.futures import FuturesSession

import requests


# We use port 1 for testing because nothing is likely to legitimately listen
# on it.
AddrValidator.DEFAULT_PORT_WHITELIST.add(1)

RequestsAPIWrapper.SUPPORT_WRAPPER_PICKLING = True
global_wrapper = RequestsAPIWrapper(
    validator=AddrValidator(
        ip_whitelist={
            ipaddress.ip_network("127.0.0.1"),
        }
    )
)
RequestsAPIWrapper.SUPPORT_WRAPPER_PICKLING = False


class _WrapperSubclass(global_wrapper.Session):
    def good_method(self):
        return "foo"


def canonname_supported():
    """Check if the nameserver supports the AI_CANONNAME flag

    travis-ci.org's Python 3 env doesn't seem to support it, so don't try
    any of the test that rely on it.
    """
    addrinfo = advocate_getaddrinfo("example.com", 0, get_canonname=True)
    assert addrinfo
    return addrinfo[0][3] == b"example.com"


def permissive_validator(**kwargs):
    default_options = dict(
        ip_blacklist=None,
        port_whitelist=None,
        port_blacklist=None,
        hostname_blacklist=None,
        allow_ipv6=True,
        allow_teredo=True,
        allow_6to4=True,
        allow_dns64=True,
        autodetect_local_addresses=False,
    )
    default_options.update(**kwargs)
    return AddrValidator(**default_options)


# Test our test wrappers to make sure they're testy
@pytest.mark.skip(reason="Requires monkeypatching socket.socket=CheckedSocket")
class TestWrapperTests(unittest.TestCase):
    def test_unsafe_connect_raises(self):
        self.assertRaises(
            DisallowedConnectException, requests.get, "http://example.org/"
        )


class ValidateIPTests(unittest.TestCase):
    def _test_ip_kind_blocked(self, ip, **kwargs):
        validator = permissive_validator(**kwargs)
        self.assertFalse(validator.is_ip_allowed(ip))

    def test_manual_ip_blacklist(self):
        """Test manually blacklisting based on IP"""
        validator = AddrValidator(
            allow_ipv6=True,
            ip_blacklist=(
                ipaddress.ip_network("132.0.5.0/24"),
                ipaddress.ip_network("152.0.0.0/8"),
                ipaddress.ip_network("::1"),
            ),
        )
        self.assertFalse(validator.is_ip_allowed("132.0.5.1"))
        self.assertFalse(validator.is_ip_allowed("152.254.90.1"))
        self.assertTrue(validator.is_ip_allowed("178.254.90.1"))
        self.assertFalse(validator.is_ip_allowed("::1"))
        # Google, found via `dig google.com AAAA`
        self.assertTrue(validator.is_ip_allowed("2607:f8b0:400a:807::200e"))

    def test_ip_whitelist(self):
        """Test manually whitelisting based on IP"""
        validator = AddrValidator(
            ip_whitelist=(ipaddress.ip_network("127.0.0.1"),),
        )
        self.assertTrue(validator.is_ip_allowed("127.0.0.1"))

    def test_ip_whitelist_blacklist_conflict(self):
        """Manual whitelist should take precedence over manual blacklist"""
        validator = AddrValidator(
            ip_whitelist=(ipaddress.ip_network("127.0.0.1"),),
            ip_blacklist=(ipaddress.ip_network("127.0.0.1"),),
        )
        self.assertTrue(validator.is_ip_allowed("127.0.0.1"))

    @unittest.skip("takes half an hour or so to run")
    def test_safecurl_blacklist(self):
        """Test that we at least disallow everything SafeCurl does"""
        # All IPs that SafeCurl would disallow
        bad_netblocks = (
            ipaddress.ip_network(x)
            for x in (
                "0.0.0.0/8",
                "10.0.0.0/8",
                "100.64.0.0/10",
                "127.0.0.0/8",
                "169.254.0.0/16",
                "172.16.0.0/12",
                "192.0.0.0/29",
                "192.0.2.0/24",
                "192.88.99.0/24",
                "192.168.0.0/16",
                "198.18.0.0/15",
                "198.51.100.0/24",
                "203.0.113.0/24",
                "224.0.0.0/4",
                "240.0.0.0/4",
            )
        )
        i = 0
        validator = AddrValidator()
        for bad_netblock in bad_netblocks:
            num_ips = bad_netblock.num_addresses
            # Don't test *every* IP in large netblocks
            step_size = int(min(max(num_ips / 255, 1), 128))
            for ip_idx in range(0, num_ips, step_size):
                i += 1
                bad_ip = bad_netblock[ip_idx]
                bad_ip_allowed = validator.is_ip_allowed(bad_ip)
                if bad_ip_allowed:
                    print(i, bad_ip)
                self.assertFalse(bad_ip_allowed)

    # TODO: something like the above for IPv6?

    def test_ipv4_mapped(self):
        self._test_ip_kind_blocked("::ffff:192.168.2.1")

    def test_teredo(self):
        # 192.168.2.1 as the client address
        self._test_ip_kind_blocked("2001:0000:4136:e378:8000:63bf:3f57:fdf2")
        # This should be disallowed even if teredo is allowed.
        self._test_ip_kind_blocked(
            "2001:0000:4136:e378:8000:63bf:3f57:fdf2",
            allow_teredo=False,
        )

    def test_ipv6(self):
        self._test_ip_kind_blocked("2002:C0A8:FFFF::", allow_ipv6=False)

    def test_sixtofour(self):
        # 192.168.XXX.XXX
        self._test_ip_kind_blocked("2002:C0A8:FFFF::")
        self._test_ip_kind_blocked("2002:C0A8:FFFF::", allow_6to4=False)

    def test_dns64(self):
        # XXX: Don't even know if this is an issue, TBH. Seems to be related
        # to DNS64/NAT64, but not a lot of easy-to-understand info:
        # https://tools.ietf.org/html/rfc6052
        self._test_ip_kind_blocked("64:ff9b::192.168.2.1")
        self._test_ip_kind_blocked("64:ff9b::192.168.2.1", allow_dns64=False)

    def test_link_local(self):
        # 169.254.XXX.XXX, AWS uses these for autoconfiguration
        self._test_ip_kind_blocked("169.254.1.1")

    def test_site_local(self):
        self._test_ip_kind_blocked("FEC0:CCCC::")

    def test_loopback(self):
        self._test_ip_kind_blocked("127.0.0.1")
        self._test_ip_kind_blocked("::1")

    def test_multicast(self):
        self._test_ip_kind_blocked("227.1.1.1")

    def test_private(self):
        self._test_ip_kind_blocked("192.168.2.1")
        self._test_ip_kind_blocked("10.5.5.5")
        self._test_ip_kind_blocked("0.0.0.0")
        self._test_ip_kind_blocked("0.1.1.1")
        self._test_ip_kind_blocked("100.64.0.0")

    def test_reserved(self):
        self._test_ip_kind_blocked("255.255.255.255")
        self._test_ip_kind_blocked("::ffff:192.168.2.1")
        # 6to4 relay
        self._test_ip_kind_blocked("192.88.99.0")

    def test_unspecified(self):
        self._test_ip_kind_blocked("0.0.0.0")

    def test_parsed(self):
        validator = permissive_validator()
        self.assertFalse(validator.is_ip_allowed(ipaddress.ip_address("0.0.0.0")))
        self.assertTrue(validator.is_ip_allowed(ipaddress.ip_address("144.1.1.1")))


class AddrInfoTests(unittest.TestCase):
    def _is_addrinfo_allowed(self, host, port, **kwargs):
        validator = permissive_validator(**kwargs)
        allowed = False
        for res in advocate_getaddrinfo(host, port):
            if validator.is_addrinfo_allowed(res):
                allowed = True
        return allowed

    def test_simple(self):
        self.assertFalse(self._is_addrinfo_allowed("192.168.0.1", 80))

    def test_malformed_addrinfo(self):
        # Alright, the addrinfo format is probably never going to change,
        # but *what if it did?*
        vl = permissive_validator()
        addrinfo = advocate_getaddrinfo("example.com", 80)[0] + (1,)
        self.assertRaises(Exception, lambda: vl.is_addrinfo_allowed(addrinfo))

    def test_unexpected_proto(self):
        # What if addrinfo returns info about a protocol we don't understand?
        vl = permissive_validator()
        addrinfo = list(advocate_getaddrinfo("example.com", 80)[0])
        addrinfo[4] = addrinfo[4] + (1,)
        self.assertRaises(Exception, lambda: vl.is_addrinfo_allowed(addrinfo))

    def test_default_port_whitelist(self):
        self.assertTrue(self._is_addrinfo_allowed("200.1.1.1", 8080))
        self.assertTrue(self._is_addrinfo_allowed("200.1.1.1", 80))
        self.assertFalse(self._is_addrinfo_allowed("200.1.1.1", 99))

    def test_port_whitelist(self):
        wl = (80, 10)
        self.assertTrue(self._is_addrinfo_allowed("200.1.1.1", 80, port_whitelist=wl))
        self.assertTrue(self._is_addrinfo_allowed("200.1.1.1", 10, port_whitelist=wl))
        self.assertFalse(self._is_addrinfo_allowed("200.1.1.1", 99, port_whitelist=wl))

    def test_port_blacklist(self):
        bl = (80, 10)
        self.assertFalse(self._is_addrinfo_allowed("200.1.1.1", 80, port_blacklist=bl))
        self.assertFalse(self._is_addrinfo_allowed("200.1.1.1", 10, port_blacklist=bl))
        self.assertTrue(self._is_addrinfo_allowed("200.1.1.1", 99, port_blacklist=bl))

    @patch("advocate.addrvalidator.determine_local_addresses")
    def test_local_address_handling(self, mock_determine_local_addresses):
        fake_addresses = [ipaddress.ip_network("200.1.1.1")]
        mock_determine_local_addresses.return_value = fake_addresses

        self.assertFalse(
            self._is_addrinfo_allowed("200.1.1.1", 80, autodetect_local_addresses=True)
        )
        # Check that `is_ip_allowed` didn't make its own call to determine
        # local addresses
        mock_determine_local_addresses.assert_called_once_with()
        mock_determine_local_addresses.reset_mock()

        self.assertTrue(
            self._is_addrinfo_allowed(
                "200.1.1.1",
                80,
                autodetect_local_addresses=False,
            )
        )
        mock_determine_local_addresses.assert_not_called()

    def test_netifaces_presence_optional(self):
        # Advocate should still work without netifaces, but only if you've specifically
        # said you don't care about checking against local interface addresses.
        with patch("advocate.addrvalidator.HAVE_NETIFACES", False):
            with self.assertRaises(ConfigException):
                self._is_addrinfo_allowed(
                    "200.1.1.1", 80, autodetect_local_addresses=True
                )
            with self.assertRaises(ConfigException):
                advocate.addrvalidator.determine_local_addresses()
            # Should be fine if you specifically asked to not look at the local addrs
            self.assertTrue(
                self._is_addrinfo_allowed(
                    "200.1.1.1",
                    80,
                    autodetect_local_addresses=False,
                )
            )

        # These shouldn't `raise`
        self._is_addrinfo_allowed("200.1.1.1", 80, autodetect_local_addresses=True)
        advocate.addrvalidator.determine_local_addresses()


@unittest.skipIf(
    not canonname_supported(),
    "Nameserver doesn't support AI_CANONNAME, skipping hostname tests",
)
class HostnameTests(unittest.TestCase):
    def setUp(self):
        self._canonname_supported = canonname_supported()

    def _is_hostname_allowed(self, host, fake_lookup=False, **kwargs):
        validator = permissive_validator(**kwargs)
        if fake_lookup:
            results = [
                (2, 1, 6, canonicalize_hostname(host).encode("utf8"), ("1.2.3.4", 80))
            ]
        else:
            results = advocate_getaddrinfo(host, 80, get_canonname=True)
        for res in results:
            if validator.is_addrinfo_allowed(res):
                return True
        return False

    def test_no_blacklist(self):
        self.assertTrue(self._is_hostname_allowed("example.com"))

    def test_idn(self):
        # test some basic globs
        self.assertFalse(
            self._is_hostname_allowed(
                "中国.example.org", fake_lookup=True, hostname_blacklist={"*.org"}
            )
        )
        # case-insensitive, please
        self.assertFalse(
            self._is_hostname_allowed(
                "中国.example.oRg", fake_lookup=True, hostname_blacklist={"*.Org"}
            )
        )
        self.assertFalse(
            self._is_hostname_allowed(
                "中国.example.org",
                fake_lookup=True,
                hostname_blacklist={"xn--fiqs8s.*.org"},
            )
        )
        self.assertFalse(
            self._is_hostname_allowed(
                "xn--fiqs8s.example.org",
                fake_lookup=True,
                hostname_blacklist={"中国.*.org"},
            )
        )
        self.assertTrue(
            self._is_hostname_allowed(
                "example.org", fake_lookup=True, hostname_blacklist={"中国.*.org"}
            )
        )
        self.assertTrue(
            self._is_hostname_allowed(
                "example.com", fake_lookup=True, hostname_blacklist={"中国.*.org"}
            )
        )
        self.assertTrue(
            self._is_hostname_allowed(
                "foo.example.org", fake_lookup=True, hostname_blacklist={"中国.*.org"}
            )
        )

    def test_missing_canonname(self):
        addrinfo = socket.getaddrinfo(
            "127.0.0.1",
            1,
            0,
            socket.SOCK_STREAM,
        )
        self.assertTrue(addrinfo)

        # Should throw an error if we're using hostname blacklisting and the
        # addrinfo record we passed in doesn't have a canonname
        validator = permissive_validator(hostname_blacklist={"foo"})
        self.assertRaises(
            NameserverException, validator.is_addrinfo_allowed, addrinfo[0]
        )

    def test_embedded_null(self):
        vl = permissive_validator(hostname_blacklist={"*.baz.com"})
        # Things get a little screwy with embedded nulls. Try to emulate any
        # possible null termination when checking if the hostname is allowed.
        self.assertFalse(vl.is_hostname_allowed("foo.baz.com\x00.example.com"))
        self.assertFalse(vl.is_hostname_allowed("foo.example.com\x00.baz.com"))
        self.assertFalse(vl.is_hostname_allowed("foo.baz.com\x00.example.com"))
        self.assertFalse(vl.is_hostname_allowed("foo.example.com\x00.baz.com"))


class ConnectionPoolingTests(unittest.TestCase):
    @patch("advocate.connection.ValidatingHTTPConnection._new_conn")
    def test_connection_reuse(self, mock_new_conn):
        # Just because you can use an existing connection doesn't mean you
        # should. The disadvantage of us working at the socket level means that
        # we get bitten if a connection pool is shared between regular requests
        # and advocate.
        # This can never happen with requests, but let's set a good example :)
        with CheckedSocket.bypass_checks():
            # HTTPBin supports `keep-alive`, so it's a good test subject
            requests.get("http://httpbin.org/")
        mock_new_conn.assert_not_called()
        try:
            advocate.get("http://httpbin.org/")
        except:
            pass
        # Requests may retry several times, but our mock doesn't return a real
        # socket. Just check that it tried to create one.
        mock_new_conn.assert_any_call()


class AdvocateWrapperTests(unittest.TestCase):
    def test_get(self):
        self.assertEqual(advocate.get("http://example.com").status_code, 200)
        self.assertEqual(advocate.get("https://example.com").status_code, 200)

    def test_validator(self):
        self.assertRaises(
            UnacceptableAddressException, advocate.get, "http://127.0.0.1/"
        )
        self.assertRaises(
            UnacceptableAddressException, advocate.get, "http://localhost/"
        )
        self.assertRaises(
            UnacceptableAddressException, advocate.get, "https://localhost/"
        )

    @unittest.skipIf(
        not canonname_supported(),
        "Nameserver doesn't support AI_CANONNAME, skipping hostname tests",
    )
    def test_blacklist_hostname(self):
        self.assertRaises(
            UnacceptableAddressException,
            advocate.get,
            "https://google.com/",
            validator=AddrValidator(hostname_blacklist={"google.com"}),
        )

    # Disabled for now because the redirection endpoint appears to be broken.
    @unittest.skip
    def test_redirect(self):
        # Make sure httpbin even works
        test_url = "http://httpbin.org/status/204"
        self.assertEqual(advocate.get(test_url).status_code, 204)

        redir_url = "http://httpbin.org/redirect-to?url=http://127.0.0.1/"
        self.assertRaises(UnacceptableAddressException, advocate.get, redir_url)

    def test_mount_disabled(self):
        sess = advocate.Session()
        self.assertRaises(
            MountDisabledException,
            sess.mount,
            "foo://",
            None,
        )

    def test_advocate_requests_api_wrapper(self):
        wrapper = RequestsAPIWrapper(validator=AddrValidator())
        local_validator = AddrValidator(
            ip_whitelist={
                ipaddress.ip_network("127.0.0.1"),
            }
        )
        local_wrapper = RequestsAPIWrapper(validator=local_validator)

        self.assertRaises(
            UnacceptableAddressException, wrapper.get, "http://127.0.0.1:1/"
        )

        with self.assertRaises(Exception) as cm:
            local_wrapper.get("http://127.0.0.1:1/")
        # Check that we got a connection exception instead of a validation one
        # This might be either exception depending on the requests version
        self.assertRegex(
            cm.exception.__class__.__name__,
            r"\A(Connection|Protocol)Error",
        )
        self.assertRaises(
            UnacceptableAddressException, wrapper.get, "http://localhost:1/"
        )
        self.assertRaises(
            UnacceptableAddressException, wrapper.get, "https://localhost:1/"
        )

    def test_advocate_default_validator_replaceable(self):
        new_validator = AddrValidator(hostname_blacklist=["example.org"])
        with patch("advocate.api.Session.DEFAULT_VALIDATOR", new_validator):
            with self.assertRaises(UnacceptableAddressException):
                advocate.get("http://example.org")

    def test_wrapper_session_pickle(self):
        # Make sure the validator still works after a pickle round-trip
        sess_instance = pickle.loads(pickle.dumps(global_wrapper.Session()))

        with self.assertRaises(Exception) as cm:
            sess_instance.get("http://127.0.0.1:1/")
        self.assertRegex(
            cm.exception.__class__.__name__,
            r"\A(Connection|Protocol)Error",
        )
        self.assertRaises(
            UnacceptableAddressException, sess_instance.get, "http://127.0.1.1:1/"
        )

    def test_wrapper_session_subclass(self):
        # Make sure pickle doesn't explode if we try to pickle a subclass
        # of `global_wrapper.Session`
        def _check_instance(instance):
            self.assertEqual(instance.good_method(), "foo")

            with self.assertRaises(Exception) as cm:
                instance.get("http://127.0.0.1:1/")
            self.assertRegex(
                cm.exception.__class__.__name__,
                r"\A(Connection|Protocol)Error",
            )
            self.assertRaises(
                UnacceptableAddressException, instance.get, "http://127.0.1.1:1/"
            )

        sess = _WrapperSubclass()
        _check_instance(sess)
        sess_unpickled = pickle.loads(pickle.dumps(sess))
        _check_instance(sess_unpickled)

    @unittest.skipIf(
        not canonname_supported(),
        "Nameserver doesn't support AI_CANONNAME, skipping hostname tests",
    )
    def test_advocate_requests_api_wrapper_hostnames(self):
        wrapper = RequestsAPIWrapper(
            validator=AddrValidator(
                hostname_blacklist={"google.com"},
            )
        )
        self.assertRaises(
            UnacceptableAddressException,
            wrapper.get,
            "https://google.com/",
        )

    @responses.activate
    def test_advocate_requests_api_wrapper_req_methods(self):
        # Make sure all the convenience methods make requests with the correct
        # methods
        wrapper = RequestsAPIWrapper(AddrValidator())

        request_methods = ("get", "options", "head", "post", "put", "patch", "delete")
        for method_name in request_methods:
            # Add a mock response for the specific method
            responses.add(
                getattr(responses, method_name.upper()),
                "http://example.com/foo",
                status=200,
            )
            # Call the wrapper method
            getattr(wrapper, method_name)("http://example.com/foo")
            # Verify the request was made with the correct method
            assert responses.calls[-1].request.method == method_name.upper()

    def test_wrapper_getattr_fallback(self):
        # Make sure wrappers include everything in Advocate's `__init__.py`
        wrapper = RequestsAPIWrapper(AddrValidator())
        self.assertIsNotNone(wrapper.PreparedRequest)

    def test_proxy_attempt_throws(self):
        # Advocate can't do anything useful when you use a proxy, the proxy
        # is the one that ultimately makes the connection
        self.assertRaises(
            NotImplementedError,
            advocate.get,
            "http://example.org/",
            proxies={
                "http": "http://example.org:3128",
                "https": "http://example.org:1080",
            },
        )

    @patch("advocate.addrvalidator.determine_local_addresses")
    def test_connect_without_local_addresses(self, mock_determine_local_addresses):
        fake_addresses = [ipaddress.ip_network("200.1.1.1")]
        mock_determine_local_addresses.return_value = fake_addresses

        validator = permissive_validator(autodetect_local_addresses=True)
        advocate.get("http://example.com/", validator=validator)
        # Check that `is_ip_allowed` didn't make its own call to determine
        # local addresses
        mock_determine_local_addresses.assert_called_once_with()
        mock_determine_local_addresses.reset_mock()

        validator = permissive_validator(autodetect_local_addresses=False)
        advocate.get("http://example.com", validator=validator)
        mock_determine_local_addresses.assert_not_called()


class AdvocateFuturesTest(unittest.TestCase):
    def test_get(self):
        sess = FuturesSession()
        assert 200 == sess.get("http://example.org/").result().status_code

    def test_custom_validator(self):
        validator = AddrValidator(hostname_blacklist={"example.org"})
        sess = FuturesSession(validator=validator)
        self.assertRaises(
            UnacceptableAddressException,
            lambda: sess.get("http://example.org").result(),
        )

    def test_many_workers(self):
        sess = FuturesSession(max_workers=50)
        self.assertRaises(
            UnacceptableAddressException,
            lambda: sess.get("http://127.0.0.1:1/").result(),
        )

    def test_passing_session(self):
        try:
            FuturesSession(session=requests.Session())
            assert False
        except NotImplementedError:
            pass

        sess = FuturesSession()
        try:
            sess.session = requests.Session()
            assert False
        except NotImplementedError:
            pass

        sess.session = advocate.Session()

    def test_advocate_wrapper_futures(self):
        wrapper = RequestsAPIWrapper(validator=AddrValidator())
        local_validator = AddrValidator(
            ip_whitelist={
                ipaddress.ip_network("127.0.0.1"),
            }
        )
        local_wrapper = RequestsAPIWrapper(validator=local_validator)

        with self.assertRaises(UnacceptableAddressException):
            sess = wrapper.FuturesSession()
            sess.get("http://127.0.0.1/").result()

        with self.assertRaises(Exception) as cm:
            sess = local_wrapper.FuturesSession()
            sess.get("http://127.0.0.1:1/").result()
        # Check that we got a connection exception instead of a validation one
        # This might be either exception depending on the requests version
        self.assertRegex(
            cm.exception.__class__.__name__,
            r"\A(Connection|Protocol)Error",
        )

        with self.assertRaises(UnacceptableAddressException):
            sess = wrapper.FuturesSession()
            sess.get("http://localhost:1/").result()
        with self.assertRaises(UnacceptableAddressException):
            sess = wrapper.FuturesSession()
            sess.get("https://localhost:1/").result()


if __name__ == "__main__":
    unittest.main()
