from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.whiteboard.models import Whiteboard


@pytest.mark.django_db
def test_get_whiteboard_returns_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    whiteboard.content = {"elements": [{"id": "abc"}], "appState": {}}
    whiteboard.save()

    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"content": {"elements": [{"id": "abc"}], "appState": {}}}


@pytest.mark.django_db
def test_get_whiteboard_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": 0})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_WHITEBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_whiteboard_permission_denied(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application()
    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})
    response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_whiteboard_unauthenticated(api_client, data_fixture):
    whiteboard = data_fixture.create_whiteboard_application()
    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})
    response = api_client.get(url, format="json")
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_put_whiteboard_persists_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})
    new_content = {
        "elements": [{"id": "rect-1", "type": "rectangle"}],
        "appState": {"viewBackgroundColor": "#fff"},
        "files": {},
    }
    response = api_client.put(
        url,
        {"content": new_content},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"content": new_content}

    refreshed = Whiteboard.objects.get(id=whiteboard.id)
    assert refreshed.content == new_content


@pytest.mark.django_db
def test_put_whiteboard_invalid_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})
    response = api_client.put(url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_put_whiteboard_permission_denied(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application()

    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})
    response = api_client.put(
        url,
        {"content": {"elements": []}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_put_whiteboard_emits_signal(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    url = reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id})

    with patch(
        "baserow.contrib.whiteboard.api.views.whiteboard_content_updated.send"
    ) as send_signal:
        response = api_client.put(
            url,
            {"content": {"elements": []}},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    assert send_signal.called
    kwargs = send_signal.call_args.kwargs
    assert kwargs["whiteboard"].id == whiteboard.id
    assert kwargs["user"].id == user.id


@pytest.mark.django_db
def test_post_broadcast_changes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    url = reverse(
        "api:whiteboard:broadcast_changes",
        kwargs={"whiteboard_id": whiteboard.id},
    )

    payload = {"type": "scene_update", "elements": [{"id": "x"}]}

    with patch(
        "baserow.contrib.whiteboard.api.views.WhiteboardPageType.broadcast"
    ) as broadcast:
        response = api_client.post(
            url,
            {"payload": payload},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert broadcast.called
    args, kwargs = broadcast.call_args
    assert args[0] == payload
    assert kwargs["whiteboard_id"] == whiteboard.id


@pytest.mark.django_db
def test_post_broadcast_changes_permission_denied(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application()

    url = reverse(
        "api:whiteboard:broadcast_changes",
        kwargs={"whiteboard_id": whiteboard.id},
    )
    response = api_client.post(
        url,
        {"payload": {"type": "scene_update"}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_post_broadcast_changes_invalid_body(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    url = reverse(
        "api:whiteboard:broadcast_changes",
        kwargs={"whiteboard_id": whiteboard.id},
    )
    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
