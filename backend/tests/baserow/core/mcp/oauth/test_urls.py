import importlib
from unittest.mock import patch

from django.http import HttpResponse
from django.urls import path

from oauth2_provider import urls as oauth2_urls

from baserow.core.mcp.oauth import urls


def test_unnamed_library_metadata_patterns_are_kept():
    unnamed = path(".well-known/unnamed", lambda request: HttpResponse())
    patterns = oauth2_urls.metadata_urlpatterns + [unnamed]
    try:
        with patch.object(oauth2_urls, "metadata_urlpatterns", patterns):
            importlib.reload(urls)
        assert unnamed in urls.metadata_patterns
    finally:
        importlib.reload(urls)
