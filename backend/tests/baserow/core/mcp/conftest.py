from unittest.mock import patch

from django.urls import get_resolver

import pytest

from tests.baserow.core.mcp.oauth.helpers import fake_cimd_fetch


@pytest.fixture(scope="session", autouse=True)
def load_urlconf_with_oauth_routes():
    # The OAuth routes are only mounted if the flag is on when the URLconf is first
    # imported, so load it before any test turns the flag off.
    get_resolver().url_patterns


@pytest.fixture(autouse=True)
def cimd_fetch():
    with patch("oauth2_provider.cimd.SafeMetadataFetcher.fetch", fake_cimd_fetch):
        yield
