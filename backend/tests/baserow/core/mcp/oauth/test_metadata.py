import pytest


@pytest.mark.django_db
def test_authorization_server_metadata(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    data = response.json()
    assert data["client_id_metadata_document_supported"] is True
    # Registration only accepts public clients.
    assert data["token_endpoint_auth_methods_supported"] == ["none"]
    assert data["registration_endpoint"].endswith("/oauth/register/")
    assert data["token_endpoint"].endswith("/oauth/token/")
    assert data["authorization_endpoint"].endswith("/oauth/authorize/")
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert "offline_access" in data["scopes_supported"]


@pytest.mark.django_db
def test_protected_resource_metadata(client, settings):
    for path in [
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
        "/.well-known/oauth-protected-resource/mcp/",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["resource"] == settings.MCP_RESOURCE_URL
        assert data["scopes_supported"] == ["mcp"]
        assert "offline_access" not in data["scopes_supported"]
        assert data["bearer_methods_supported"] == ["header"]


@pytest.mark.django_db
@pytest.mark.parametrize("suffix", ["", "/"])
def test_protected_resource_metadata_of_the_old_endpoint_url(client, settings, suffix):
    # Clients accept the `/mcp` document for any URL under it, so the old URL
    # names itself and the consent page can offer only its endpoint's tools.
    response = client.get(
        f"/.well-known/oauth-protected-resource/mcp/some-endpoint-key/sse{suffix}"
    )
    assert response.status_code == 200
    # Names the URL exactly as asked, because the client compares the two.
    assert response.json()["resource"] == (
        f"{settings.MCP_RESOURCE_URL}/some-endpoint-key/sse{suffix}"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/.well-known/oauth-protected-resource/other",
        "/.well-known/oauth-protected-resource/mcp/a/b",
    ],
)
def test_protected_resource_metadata_of_other_paths_is_the_mcp_one(
    client, settings, path
):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["resource"] == settings.MCP_RESOURCE_URL


@pytest.mark.django_db
def test_openai_apps_challenge_returns_the_token(client, settings):
    settings.BASEROW_MCP_OPENAI_APPS_CHALLENGE = "challenge-token"
    response = client.get("/.well-known/openai-apps-challenge")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert response.content == b"challenge-token"


@pytest.mark.django_db
def test_openai_apps_challenge_is_not_found_without_a_token(client, settings):
    settings.BASEROW_MCP_OPENAI_APPS_CHALLENGE = ""
    response = client.get("/.well-known/openai-apps-challenge")
    assert response.status_code == 404
