from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.whiteboard.comments.models import WhiteboardComment


def _doc(text="hi"):
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


@pytest.mark.django_db
def test_list_comments(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    a = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)
    b = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)
    a_reply = data_fixture.create_whiteboard_comment(
        user=user, whiteboard=whiteboard, parent_comment=a
    )

    url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert resp.status_code == HTTP_200_OK
    ids = [c["id"] for c in resp.json()]
    assert ids == [a.id, a_reply.id, b.id]


@pytest.mark.django_db
def test_create_top_level_comment(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.post(
        url,
        {"message": _doc("hello"), "x": 12.5, "y": -3.0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp.status_code == HTTP_200_OK
    body = resp.json()
    assert body["x"] == 12.5
    assert body["y"] == -3.0
    assert body["parent_comment_id"] is None
    assert WhiteboardComment.objects.filter(id=body["id"]).exists()


@pytest.mark.django_db
def test_create_reply(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    parent = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)

    url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.post(
        url,
        {"message": _doc("reply"), "parent_comment_id": parent.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp.status_code == HTTP_200_OK
    body = resp.json()
    assert body["parent_comment_id"] == parent.id
    assert body["x"] is None and body["y"] is None


@pytest.mark.django_db
def test_create_invalid_prosemirror(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.post(
        url,
        {"message": {"foo": "bar"}, "x": 0, "y": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_create_unauthenticated(api_client, data_fixture):
    whiteboard = data_fixture.create_whiteboard_application()
    url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.post(url, {"message": _doc(), "x": 0, "y": 0}, format="json")
    assert resp.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_update_only_author(api_client, data_fixture):
    author, author_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=author)
    intruder, intruder_token = data_fixture.create_user_and_token()
    data_fixture.create_user_workspace(user=intruder, workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)
    comment = data_fixture.create_whiteboard_comment(user=author, whiteboard=whiteboard)

    url = reverse("api:whiteboard:comments:item", kwargs={"comment_id": comment.id})
    resp = api_client.patch(
        url,
        {"message": _doc("nope")},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {intruder_token}",
    )
    assert resp.status_code == HTTP_401_UNAUTHORIZED

    resp = api_client.patch(
        url,
        {"message": _doc("yes")},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {author_token}",
    )
    assert resp.status_code == HTTP_200_OK
    comment.refresh_from_db()
    assert comment.message["content"][0]["content"][0]["text"] == "yes"


@pytest.mark.django_db
def test_delete_only_author(api_client, data_fixture):
    author, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=author)
    comment = data_fixture.create_whiteboard_comment(user=author, whiteboard=whiteboard)

    url = reverse("api:whiteboard:comments:item", kwargs={"comment_id": comment.id})
    resp = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert resp.status_code == HTTP_204_NO_CONTENT
    assert not WhiteboardComment.objects.filter(id=comment.id).exists()


@pytest.mark.django_db
def test_delete_does_not_exist(api_client, data_fixture):
    _, token = data_fixture.create_user_and_token()
    url = reverse("api:whiteboard:comments:item", kwargs={"comment_id": 999999})
    resp = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert resp.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_resolve_top_level(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    comment = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)

    url = reverse("api:whiteboard:comments:resolve", kwargs={"comment_id": comment.id})
    resp = api_client.post(
        url, {"resolved": True}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert resp.status_code == HTTP_200_OK
    body = resp.json()
    assert body["resolved"] is True
    assert body["resolved_by_id"] == user.id
    assert body["resolved_at"] is not None


@pytest.mark.django_db
def test_resolve_rejects_reply(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    parent = data_fixture.create_whiteboard_comment(user=user, whiteboard=whiteboard)
    reply = data_fixture.create_whiteboard_comment(
        user=user, whiteboard=whiteboard, parent_comment=parent
    )

    url = reverse("api:whiteboard:comments:resolve", kwargs={"comment_id": reply.id})
    resp = api_client.post(
        url, {"resolved": True}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert resp.status_code == HTTP_400_BAD_REQUEST
