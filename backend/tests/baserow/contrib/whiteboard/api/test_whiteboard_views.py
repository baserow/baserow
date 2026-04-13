from unittest.mock import patch

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)


# ---------------------------------------------------------------------------
# GET /api/whiteboard/{id}/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_whiteboard_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(
        user=user,
        content={"store": {"shapes": [{"id": "shape:1"}]}},
    )

    response = api_client.get(
        f"/api/whiteboard/{whiteboard.id}/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["content"] == {"store": {"shapes": [{"id": "shape:1"}]}}


@pytest.mark.django_db
def test_get_whiteboard_content_empty(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    response = api_client.get(
        f"/api/whiteboard/{whiteboard.id}/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["content"] == {}


@pytest.mark.django_db
def test_get_whiteboard_content_unauthorized(api_client, data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    response = api_client.get(f"/api/whiteboard/{whiteboard.id}/")

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_whiteboard_content_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.get(
        "/api/whiteboard/99999/",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_get_whiteboard_content_other_user_in_workspace(api_client, data_fixture):
    """A workspace member who didn't create the whiteboard can still read it."""

    user = data_fixture.create_user()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user, members=[other_user])
    whiteboard = data_fixture.create_whiteboard_application(
        workspace=workspace,
        content={"data": True},
    )

    response = api_client.get(
        f"/api/whiteboard/{whiteboard.id}/",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["content"] == {"data": True}


# ---------------------------------------------------------------------------
# PUT /api/whiteboard/{id}/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_whiteboard_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    new_content = {"store": {"shapes": [{"id": "shape:2", "type": "draw"}]}}
    response = api_client.put(
        f"/api/whiteboard/{whiteboard.id}/",
        {"content": new_content},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["content"] == new_content

    # Verify it was persisted
    whiteboard.refresh_from_db()
    assert whiteboard.content == new_content


@pytest.mark.django_db
def test_save_whiteboard_content_unauthorized(api_client, data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    response = api_client.put(
        f"/api/whiteboard/{whiteboard.id}/",
        {"content": {}},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_save_whiteboard_content_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.put(
        "/api/whiteboard/99999/",
        {"content": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_save_whiteboard_content_missing_content_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    response = api_client.put(
        f"/api/whiteboard/{whiteboard.id}/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_save_whiteboard_overwrites_previous_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(
        user=user,
        content={"old": "data"},
    )

    new_content = {"new": "data"}
    response = api_client.put(
        f"/api/whiteboard/{whiteboard.id}/",
        {"content": new_content},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    whiteboard.refresh_from_db()
    assert whiteboard.content == new_content
    assert "old" not in whiteboard.content


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_save_whiteboard_broadcasts_content_updated(
    mock_broadcast_to_channel_group, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    new_content = {"store": {"shapes": []}}
    api_client.put(
        f"/api/whiteboard/{whiteboard.id}/",
        {"content": new_content},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"whiteboard-{whiteboard.id}"
    assert args[0][1]["type"] == "whiteboard_content_updated"
    assert args[0][1]["whiteboard_id"] == whiteboard.id


# ---------------------------------------------------------------------------
# POST /api/whiteboard/{id}/broadcast-changes/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_broadcast_changes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    changes = {
        "added": {"shape:1": {"id": "shape:1", "type": "draw"}},
        "updated": {},
        "removed": {},
    }
    response = api_client.post(
        f"/api/whiteboard/{whiteboard.id}/broadcast-changes/",
        {"changes": changes},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_broadcast_changes_does_not_persist(api_client, data_fixture):
    """Broadcasting changes should not modify the stored content."""

    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(
        user=user, content={"original": True}
    )

    api_client.post(
        f"/api/whiteboard/{whiteboard.id}/broadcast-changes/",
        {"changes": {"added": {"shape:1": {"id": "shape:1"}}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    whiteboard.refresh_from_db()
    assert whiteboard.content == {"original": True}


@pytest.mark.django_db
def test_broadcast_changes_unauthorized(api_client, data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    response = api_client.post(
        f"/api/whiteboard/{whiteboard.id}/broadcast-changes/",
        {"changes": {}},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_broadcast_changes_not_found(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    response = api_client.post(
        "/api/whiteboard/99999/broadcast-changes/",
        {"changes": {}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_broadcast_changes_missing_changes_field(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    response = api_client.post(
        f"/api/whiteboard/{whiteboard.id}/broadcast-changes/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_broadcast_changes_sends_ws_message(
    mock_broadcast_to_channel_group, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    changes = {
        "added": {"shape:1": {"id": "shape:1", "type": "draw", "x": 10, "y": 20}},
        "updated": {
            "shape:2": [
                {"id": "shape:2", "x": 0},
                {"id": "shape:2", "x": 100},
            ]
        },
        "removed": {"shape:3": {"id": "shape:3"}},
    }
    api_client.post(
        f"/api/whiteboard/{whiteboard.id}/broadcast-changes/",
        {"changes": changes},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"whiteboard-{whiteboard.id}"
    assert args[0][1]["type"] == "whiteboard_changes"
    assert args[0][1]["whiteboard_id"] == whiteboard.id
    assert args[0][1]["changes"] == changes
