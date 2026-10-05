from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.core.skills.models import WorkspaceSkill


@pytest.mark.django_db(transaction=True)
def test_workspace_skill_crud(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    other_user, other_token = data_fixture.create_user_and_token()
    list_url = reverse("api:skills:workspace", kwargs={"workspace_id": workspace.id})

    with patch("baserow.ws.signals.broadcast_to_permitted_users.delay") as bcast:
        response = api_client.post(
            list_url,
            {
                "name": "Formula conventions",
                "description": "Use when writing formulas.",
                "content": "# Formulas\n\nPrefer `field()` references.",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK, response.json()
    skill = response.json()
    assert skill["name"] == "Formula conventions"
    assert skill["workspace_id"] == workspace.id
    assert skill["created_by_id"] == user.id
    assert bcast.call_args.args[4]["type"] == "workspace_skill_created"

    # The same name twice in a workspace is refused.
    response = api_client.post(
        list_url,
        {"name": "Formula conventions"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_WORKSPACE_SKILL_NAME_NOT_UNIQUE"

    response = api_client.get(list_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_200_OK
    assert [s["name"] for s in response.json()] == ["Formula conventions"]

    item_url = reverse("api:skills:item", kwargs={"skill_id": skill["id"]})
    with patch("baserow.ws.signals.broadcast_to_permitted_users.delay") as bcast:
        response = api_client.patch(
            item_url,
            {"content": "Updated"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["content"] == "Updated"
    assert response.json()["name"] == "Formula conventions"
    assert bcast.call_args.args[4]["type"] == "workspace_skill_updated"

    # Strangers to the workspace get nothing.
    response = api_client.get(list_url, HTTP_AUTHORIZATION=f"JWT {other_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    response = api_client.patch(
        item_url,
        {"content": "Hacked"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    with patch("baserow.ws.signals.broadcast_to_permitted_users.delay") as bcast:
        response = api_client.delete(item_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_204_NO_CONTENT
    assert bcast.call_args.args[4] == {
        "type": "workspace_skill_deleted",
        "workspace_id": workspace.id,
        "skill_id": skill["id"],
    }
    assert not WorkspaceSkill.objects.filter(id=skill["id"]).exists()

    response = api_client.get(item_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WORKSPACE_SKILL_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_workspace_skill_validation(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    list_url = reverse("api:skills:workspace", kwargs={"workspace_id": workspace.id})

    response = api_client.post(
        list_url,
        {"description": "no name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        list_url,
        {"name": "x", "content": "y" * 50001},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    response = api_client.get(
        reverse("api:skills:workspace", kwargs={"workspace_id": 999999}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
