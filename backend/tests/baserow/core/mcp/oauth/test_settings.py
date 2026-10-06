import runpy
from pathlib import Path

import baserow.config.settings.base as base_settings


def test_trailing_slash_in_public_backend_url_is_stripped(monkeypatch):
    monkeypatch.setenv("BASEROW_PUBLIC_URL", "")
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://baserow.example/")
    settings = runpy.run_path(str(Path(base_settings.__file__)))

    assert settings["MCP_RESOURCE_URL"] == "https://baserow.example/mcp"
    oauth = settings["OAUTH2_PROVIDER"]
    assert oauth["OIDC_ISS_ENDPOINT"] == "https://baserow.example"
    assert oauth["OAUTH2_PROTECTED_RESOURCE_IDENTIFIER"] == (
        "https://baserow.example/mcp"
    )
    assert oauth["OAUTH2_PROTECTED_RESOURCE_AUTHORIZATION_SERVERS"] == [
        "https://baserow.example"
    ]
