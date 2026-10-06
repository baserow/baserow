import pytest


@pytest.mark.django_db
def test_authorization_server_metadata(client):
    response = client.get("/.well-known/oauth-authorization-server")
    assert response.status_code == 200
    data = response.json()
    assert data["client_id_metadata_document_supported"] is True
    assert "none" in data["token_endpoint_auth_methods_supported"]
    assert data["registration_endpoint"].endswith("/oauth/register/")
    assert data["token_endpoint"].endswith("/oauth/token/")
    assert data["authorization_endpoint"].endswith("/oauth/authorize/")
    assert data["code_challenge_methods_supported"] == ["S256"]


@pytest.mark.django_db
def test_protected_resource_metadata(client, settings):
    for path in [
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["resource"] == settings.MCP_RESOURCE_URL
        assert data["scopes_supported"] == ["mcp"]
        assert data["bearer_methods_supported"] == ["header"]
