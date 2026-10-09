import base64
import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.urls import reverse

import pytest
from oauth2_provider.models import AccessToken, get_application_model

from baserow.core.mcp.models import MCPEndpoint
from tests.baserow.core.mcp.oauth.helpers import (
    REDIRECT_URI,
    authorize_query,
    cimd_client,
    enabled_tool_names,
    obtain_tokens,
    pkce_pair,
)

ISSUER = settings.OAUTH2_PROVIDER["OIDC_ISS_ENDPOINT"]


def allow_body(query, workspace, tools=None):
    return {
        "query": query,
        "allow": True,
        "workspace_id": workspace.id,
        "tools": enabled_tool_names() if tools is None else tools,
    }


def post_consent(api_client, token, body):
    return api_client.post(
        reverse("api:mcp:oauth_consent"),
        body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_authorize_redirects_to_frontend_consent(client):
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge)
    response = client.get(f"/oauth/authorize/?{query}")
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert response["Location"].startswith(settings.PUBLIC_WEB_FRONTEND_URL)
    assert location.path == "/mcp-authorize"
    # The query travels base64url-encoded, unpadded, so the login round trip
    # (encodeURI + router) can't re-encode it.
    params = parse_qs(location.query)
    assert list(params) == ["request"]
    encoded = params["request"][0]
    assert re.fullmatch(r"[A-Za-z0-9_-]+", encoded)
    padded = encoded + "=" * (-len(encoded) % 4)
    assert base64.urlsafe_b64decode(padded).decode() == query


def without_param(query, name):
    params = parse_qs(query)
    params.pop(name)
    return urlencode(params, doseq=True)


def assert_redirects_with_error(response, error):
    assert response.status_code == 302
    assert response["Location"].startswith(REDIRECT_URI)
    assert "/mcp-authorize" not in response["Location"]
    query = parse_qs(urlparse(response["Location"]).query)
    assert query["error"] == [error]
    assert query["state"] == ["s1"]
    assert query["iss"] == [ISSUER]


@pytest.mark.django_db
def test_authorize_without_pkce_is_rejected(client):
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = without_param(authorize_query(client_id, challenge), "code_challenge")
    response = client.get(f"/oauth/authorize/?{query}")
    assert_redirects_with_error(response, "invalid_request")


@pytest.mark.django_db
def test_authorize_rejects_plain_challenge_method(client):
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge).replace("S256", "plain")
    response = client.get(f"/oauth/authorize/?{query}")
    assert_redirects_with_error(response, "invalid_request")


@pytest.mark.django_db
def test_authorize_rejects_foreign_resource(client):
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge) + "&resource=https%3A%2F%2Fevil.test"
    response = client.get(f"/oauth/authorize/?{query}")
    assert_redirects_with_error(response, "invalid_target")


@pytest.mark.django_db
def test_consent_post_rejects_plain_challenge_method(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge).replace("S256", "plain")
    response = post_consent(
        api_client,
        token,
        allow_body(query, workspace),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


@pytest.mark.django_db
def test_consent_post_rejects_foreign_resource(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = authorize_query(client_id, challenge) + "&resource=https%3A%2F%2Fevil.test"
    response = post_consent(
        api_client,
        token,
        allow_body(query, workspace),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_target"


@pytest.mark.django_db
def test_consent_get_without_redirect_uri_uses_registered_one(
    client, api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    query = without_param(authorize_query(client_id, challenge), "redirect_uri")
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": query},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    assert response.json()["redirect_host"] == "127.0.0.1"


@pytest.mark.django_db
def test_missing_resource_is_pinned_to_mcp_resource(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    verifier, challenge = pkce_pair()
    query = without_param(authorize_query(client_id, challenge), "resource")
    response = post_consent(
        api_client,
        token,
        allow_body(query, workspace),
    )
    assert response.status_code == 200
    code = parse_qs(urlparse(response.json()["redirect_url"]).query)["code"][0]
    response = client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert response.status_code == 200, response.content
    checksum = hashlib.sha256(response.json()["access_token"].encode()).hexdigest()
    access = AccessToken.objects.get(token_checksum=checksum)
    assert access.allows_audience(settings.MCP_RESOURCE_URL)


@pytest.mark.django_db
def test_authorize_unknown_client_shows_the_error_on_the_consent_page(client):
    _, challenge = pkce_pair()
    response = client.get(f"/oauth/authorize/?{authorize_query('nope', challenge)}")
    assert response.status_code == 302
    location = urlparse(response["Location"])
    assert response["Location"].startswith(settings.PUBLIC_WEB_FRONTEND_URL)
    assert location.path == "/mcp-authorize"
    # Only a code: the page maps it to its own text, so the URL can't inject any.
    assert parse_qs(location.query) == {"error": ["unknown_client"]}
    assert REDIRECT_URI not in response["Location"]


@pytest.mark.django_db
def test_consent_get_cimd_client_is_named_by_its_metadata(
    client, api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()
    _, challenge = pkce_pair()
    client_id = cimd_client(client, client_name="Claude Code")
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    assert response.json()["client_name"] == "Claude Code"


@pytest.mark.django_db
def test_consent_get_nameless_cimd_client_is_named_by_its_host(
    client, api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token()
    _, challenge = pkce_pair()
    # The redirect host (127.0.0.1) is not who published the metadata.
    client_id = cimd_client(client, client_name="")
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    assert response.json()["client_name"] == "claude.ai"


@pytest.mark.django_db
def test_consent_get_lists_workspaces_and_enabled_tools(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user, name="One")
    workspace_2 = data_fixture.create_workspace(user=user, name="Two")
    other = data_fixture.create_workspace(name="Not mine")
    data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_application(workspace=workspace_1)
    trashed = data_fixture.create_database_application(
        workspace=workspace_1, trashed=True
    )
    data_fixture.create_database_application(workspace=other)
    assert trashed.trashed
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query(client_id, challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["client_name"] == "Test MCP client"
    assert data["client_id"] == client_id
    assert data["redirect_host"] == "127.0.0.1"
    assert "endpoints" not in data
    assert data["verified"] is True
    assert data["verified_host"] == "claude.ai"
    assert data["workspaces"] == [
        {"id": workspace_1.id, "name": "One", "database_count": 2},
        {"id": workspace_2.id, "name": "Two", "database_count": 0},
    ]
    tools = {tool["name"]: tool for tool in data["tools"]}
    assert [tool["name"] for tool in data["tools"]] == enabled_tool_names()
    # Disabled tools are never offered.
    assert "delete_table" not in tools
    assert tools["list_tables"] == {
        "name": "list_tables",
        "title": "List tables",
        "read_only": True,
        "destructive": False,
    }
    assert tools["delete_rows"]["read_only"] is False
    assert tools["delete_rows"]["destructive"] is True


@pytest.mark.django_db
def test_consent_get_invalid_query(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": "client_id=nope"},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_full_flow_issues_endpoint_bound_token(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    tokens = obtain_tokens(client, api_client, token, workspace)
    endpoint = MCPEndpoint.objects.get(user=user, workspace=workspace)
    assert tokens["endpoint_id"] == endpoint.id
    checksum = hashlib.sha256(tokens["access_token"].encode()).hexdigest()
    access = AccessToken.objects.get(token_checksum=checksum)
    assert set(access.scope.split()) == {"mcp", f"endpoint:{endpoint.id}"}
    assert access.user_id == user.id
    assert access.allows_audience(settings.MCP_RESOURCE_URL)
    assert tokens["refresh_token"]


@pytest.mark.django_db
def test_consent_deny_returns_access_denied(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        {"query": authorize_query(client_id, challenge), "allow": False},
    )
    assert response.status_code == 200
    redirect_url = response.json()["redirect_url"]
    assert redirect_url.startswith("http://127.0.0.1:33418/callback")
    query = parse_qs(urlparse(redirect_url).query)
    assert query["error"] == ["access_denied"]
    assert query["state"] == ["s1"]
    assert query["iss"] == [ISSUER]


@pytest.mark.django_db
def test_consent_creates_grant_with_allowed_tools(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        allow_body(
            authorize_query(client_id, challenge),
            workspace,
            # Stored in registry order whatever order the client sends.
            ["list_table_rows", "list_tables"],
        ),
    )
    assert response.status_code == 200, response.content
    redirect = parse_qs(urlparse(response.json()["redirect_url"]).query)
    assert redirect["code"]
    endpoint = MCPEndpoint.objects.get(user=user)
    assert endpoint.workspace_id == workspace.id
    assert endpoint.name == "Test MCP client"
    assert endpoint.allowed_tools == ["list_tables", "list_table_rows"]


@pytest.mark.django_db
def test_consent_reuses_grant_for_same_client_and_workspace(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    first = obtain_tokens(
        client, api_client, token, workspace, ["list_tables"], client_id=client_id
    )
    second = obtain_tokens(
        client,
        api_client,
        token,
        workspace,
        ["list_databases", "list_tables"],
        client_id=client_id,
    )
    assert first["endpoint_id"] == second["endpoint_id"]
    endpoint = MCPEndpoint.objects.get(user=user)
    assert endpoint.oauth_client_id == client_id
    assert endpoint.allowed_tools == ["list_databases", "list_tables"]
    # Another workspace gets its own grant.
    third = obtain_tokens(
        client, api_client, token, other_workspace, client_id=client_id
    )
    assert third["endpoint_id"] != first["endpoint_id"]
    assert MCPEndpoint.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_consent_never_reuses_a_manual_endpoint(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    manual = data_fixture.create_mcp_endpoint(
        user=user, workspace=workspace, name="Test MCP client"
    )
    tokens = obtain_tokens(client, api_client, token, workspace, ["list_tables"])
    assert tokens["endpoint_id"] != manual.id
    manual.refresh_from_db()
    assert manual.allowed_tools is None
    assert manual.oauth_client_id is None
    assert MCPEndpoint.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_clients_with_the_same_name_get_separate_grants(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    first = obtain_tokens(client, api_client, token, workspace, ["list_tables"])
    second = obtain_tokens(client, api_client, token, workspace, ["list_databases"])
    assert first["client_id"] != second["client_id"]
    assert first["endpoint_id"] != second["endpoint_id"]
    first_endpoint = MCPEndpoint.objects.get(id=first["endpoint_id"])
    second_endpoint = MCPEndpoint.objects.get(id=second["endpoint_id"])
    assert first_endpoint.name == second_endpoint.name == "Test MCP client"
    assert first_endpoint.oauth_client_id == first["client_id"]
    assert first_endpoint.allowed_tools == ["list_tables"]
    assert second_endpoint.oauth_client_id == second["client_id"]
    assert second_endpoint.allowed_tools == ["list_databases"]


@pytest.mark.django_db
def test_long_client_name_is_cut_to_the_endpoint_name_length(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client, client_name="x" * 150)
    obtain_tokens(client, api_client, token, workspace, client_id=client_id)
    assert MCPEndpoint.objects.get(user=user).name == "x" * 100


@pytest.mark.parametrize(
    "tools",
    [
        [],
        ["does_not_exist"],
        # Disabled tools can't be granted.
        ["delete_table"],
        ["list_tables", "list_tables"],
        "list_tables",
        None,
    ],
)
@pytest.mark.django_db
def test_consent_rejects_invalid_tools(client, api_client, data_fixture, tools):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    body = allow_body(authorize_query(client_id, challenge), workspace)
    if tools is None:
        del body["tools"]
    else:
        body["tools"] = tools
    response = post_consent(api_client, token, body)
    assert response.status_code == 400, response.content
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_allow_requires_workspace(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    body = allow_body(authorize_query(client_id, challenge), workspace)
    del body["workspace_id"]
    response = post_consent(api_client, token, body)
    assert response.status_code == 400
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_unknown_workspace_is_rejected(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    body = {
        "query": authorize_query(client_id, challenge),
        "allow": True,
        "workspace_id": 999999,
        "tools": ["list_tables"],
    }
    response = post_consent(api_client, token, body)
    assert response.status_code == 404
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_cannot_grant_foreign_workspace(client, api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    foreign_workspace = data_fixture.create_workspace()
    client_id = cimd_client(client)
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        allow_body(authorize_query(client_id, challenge), foreign_workspace),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_cannot_reuse_grant_after_leaving_workspace(
    client, api_client, data_fixture
):
    owner = data_fixture.create_user()
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=owner, members=[user])
    client_id = cimd_client(client)
    obtain_tokens(
        client, api_client, token, workspace, ["list_tables"], client_id=client_id
    )
    workspace.workspaceuser_set.filter(user=user).delete()
    _, challenge = pkce_pair()
    response = post_consent(
        api_client,
        token,
        allow_body(authorize_query(client_id, challenge), workspace),
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert MCPEndpoint.objects.get(user=user).allowed_tools == ["list_tables"]


@pytest.mark.django_db
def test_consent_invalid_query_does_not_create_endpoint(
    client, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    response = post_consent(api_client, token, allow_body("client_id=nope", workspace))
    assert response.status_code == 400
    assert not MCPEndpoint.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_consent_requires_authentication(api_client):
    response = api_client.get(reverse("api:mcp:oauth_consent"))
    assert response.status_code == 401


@pytest.mark.django_db
def test_consent_get_manual_client_is_not_verified(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    Application = get_application_model()
    Application.objects.create(
        client_id="manual-client",
        name="Manual",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=REDIRECT_URI,
        registration_source=Application.RegistrationSource.MANUAL,
    )
    _, challenge = pkce_pair()
    response = api_client.get(
        reverse("api:mcp:oauth_consent"),
        {"query": authorize_query("manual-client", challenge)},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.content
    assert response.json()["verified"] is False
    assert response.json()["verified_host"] is None


@pytest.mark.django_db
def test_authorize_redirect_has_no_double_slash(client, settings):
    settings.PUBLIC_WEB_FRONTEND_URL = "https://br.example/"
    _, challenge = pkce_pair()
    query = authorize_query(cimd_client(client), challenge)
    response = client.get(f"/oauth/authorize/?{query}")
    assert response.status_code == 302
    assert response["Location"].startswith("https://br.example/mcp-authorize?")
