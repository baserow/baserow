import pytest
import requests


@pytest.fixture(autouse=True)
def bypass_ssrf_for_httpretty(monkeypatch):
    """
    Replace ssrf_safe_request with the plain requests module for user file
    API tests. The SSRF adapter rewrites hostnames to resolved IPs, which
    is incompatible with httpretty's fake SSL certificates for HTTPS URLs.
    SSRF protection itself is covered by dedicated tests in tests/baserow/core/ssrf/.
    """

    monkeypatch.setattr("baserow.core.user_files.handler.ssrf_safe_request", requests)
