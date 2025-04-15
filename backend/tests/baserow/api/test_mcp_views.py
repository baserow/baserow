from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.mcp.models import MCPEndpoint


@pytest.mark.django_db
def test_list_endpoints(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_2 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_3 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)

    url = reverse("api:mcp:list_endpoints")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT random")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:mcp:list_endpoints")
    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3

    assert response_json[0]["id"] == endpoint_1.id
    assert response_json[0]["name"] == endpoint_1.name
    assert response_json[0]["key"] == endpoint_1.key
    assert response_json[0]["workspace_id"] == endpoint_1.workspace.id
    assert response_json[0]["workspace_name"] == endpoint_1.workspace.name

    assert response_json[1]["id"] == endpoint_2.id
    assert response_json[1]["name"] == endpoint_2.name
    assert response_json[1]["key"] == endpoint_2.key
    assert response_json[1]["workspace_id"] == endpoint_2.workspace.id
    assert response_json[1]["workspace_name"] == endpoint_2.workspace.name

    assert response_json[2]["id"] == endpoint_3.id
    assert response_json[2]["name"] == endpoint_3.name
    assert response_json[2]["key"] == endpoint_3.key
    assert response_json[2]["workspace_id"] == endpoint_3.workspace.id
    assert response_json[2]["workspace_name"] == endpoint_3.workspace.name


@pytest.mark.django_db
def test_create_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    url = reverse("api:mcp:list_endpoints")
    response = api_client.post(
        url,
        {"name": "Test 1", "workspace_id": workspace_1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT random",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:mcp:list_endpoints")
    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"]["name"][0]["code"] == "required"
    assert response_json["detail"]["workspace_id"][0]["code"] == "required"

    url = reverse("api:mcp:list_endpoints")
    response = api_client.post(
        url,
        {"name": "Test", "workspace_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:mcp:list_endpoints")
    response = api_client.post(
        url,
        {
            "name": "Test",
            "workspace_id": workspace_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:mcp:list_endpoints")
    response = api_client.post(
        url,
        {"name": "Test", "workspace_id": workspace_1.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert MCPEndpoint.objects.all().count() == 1
    endpoint = MCPEndpoint.objects.all().first()
    assert response_json["id"] == endpoint.id
    assert response_json["name"] == endpoint.name
    assert response_json["workspace_id"] == endpoint.workspace_id == workspace_1.id
    assert response_json["key"] == endpoint.key
    assert len(response_json["key"]) == 32


@pytest.mark.django_db
def test_get_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_2 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)
    endpoint_3 = data_fixture.create_mcp_endpoint()

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_1.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT random")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": 99999})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_3.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_2.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_1.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] == endpoint_1.id
    assert response_json["name"] == endpoint_1.name
    assert response_json["workspace_id"] == endpoint_1.workspace_id
    assert response_json["key"] == endpoint_1.key
    assert len(response_json["key"]) == 32


@pytest.mark.django_db
def test_update_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_2 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)
    endpoint_3 = data_fixture.create_mcp_endpoint()

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_1.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT random"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": 99999})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_3.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_2.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_2.id})
    response = api_client.patch(
        url, {"name": ""}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["detail"]["name"][0]["code"] == "blank"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_3.id})
    response = api_client.patch(
        url, {"name": "test"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_1.id})
    response = api_client.patch(
        url, {"name": "New name"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    endpoint_1.refresh_from_db()
    assert response_json["id"] == endpoint_1.id
    assert response_json["name"] == "New name" == endpoint_1.name
    assert response_json["workspace_id"] == endpoint_1.workspace_id
    assert response_json["key"] == endpoint_1.key
    assert len(response_json["key"]) == 32


@pytest.mark.django_db
def test_delete_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_2 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)
    endpoint_3 = data_fixture.create_mcp_endpoint()

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_1.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT random")
    assert response.status_code == HTTP_401_UNAUTHORIZED

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": 99999})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_3.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_2.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_3.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"

    assert MCPEndpoint.objects.all().count() == 3

    url = reverse("api:mcp:endpoint", kwargs={"endpoint_id": endpoint_1.id})
    response = api_client.delete(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT

    assert MCPEndpoint.objects.all().count() == 2
