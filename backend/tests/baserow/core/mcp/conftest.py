from unittest.mock import patch

import pytest

from tests.baserow.core.mcp.oauth.helpers import fake_cimd_fetch


@pytest.fixture(autouse=True)
def cimd_fetch():
    with patch("oauth2_provider.cimd.SafeMetadataFetcher.fetch", fake_cimd_fetch):
        yield
