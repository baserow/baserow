from django.conf import settings
from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)
from rest_framework_simplejwt.tokens import RefreshToken

from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
def test_user_outside_workspace_cannot_see_notifications(data_fixture, api_client):
    _, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_user_cannot_see_notifications_of_non_existing_workspace(
    data_fixture, api_client
):
    _, token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": 999}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_user_can_see_notifications_paginated(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    notifications_count = settings.ROW_PAGE_SIZE_LIMIT + 2

    for _ in range(notifications_count):
        data_fixture.create_workspace_notification_for_users(
            workspace=workspace, recipients=[user], notification_type="test"
        )

    # Offset 0 and limit as by default.
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == notifications_count
    assert len(response.json()["results"]) == settings.ROW_PAGE_SIZE_LIMIT

    # Offset a page and limit=1.
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id})
        + f"?offset={settings.ROW_PAGE_SIZE_LIMIT}&limit=1",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == notifications_count
    assert len(response.json()["results"]) == 1

    # Offset a page and limit as by default.
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id})
        + f"?offset={settings.ROW_PAGE_SIZE_LIMIT}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == notifications_count
    assert len(response.json()["results"]) == 2


@pytest.mark.django_db
def test_user_get_unread_workspace_count_listing_workspaces(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    with freeze_time("2021-01-01 12:00"):
        data_fixture.create_workspace_notification_for_users(
            workspace=workspace, recipients=[user]
        )

    response = api_client.get(
        reverse("api:workspaces:list"),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()[0]["unread_notifications_count"] == 1


@pytest.mark.django_db
def test_user_get_unread_user_count_refreshing_token(data_fixture, api_client):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@test.nl", password="password")

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@test.nl", "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["user_notifications"]["unread_count"] == 0

    refresh_token = str(RefreshToken.for_user(user))
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["user_notifications"]["unread_count"] == 0

    data_fixture.create_user_notification_for_users(recipients=[user])

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@test.nl", "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["user_notifications"]["unread_count"] == 1

    refresh_token = str(RefreshToken.for_user(user))
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["user_notifications"]["unread_count"] == 1


@pytest.mark.django_db
def test_user_fetch_workspace_and_user_notifications_together(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    with freeze_time("2021-01-01 12:00"):
        data_fixture.create_workspace_notification_for_users(
            sender=user,
            workspace=workspace,
            recipients=[user],
            notification_type="fake_application_notification",
        )
    with freeze_time("2021-01-01 12:01"):
        data_fixture.create_user_notification_for_users(
            recipients=[user],
            notification_type="version_update",
            data={"version": "1.0.0"},
        )

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 2
    assert response.json()["results"] == [
        {
            "id": AnyInt(),
            "sender": None,
            "created_on": "2021-01-01T12:01:00Z",
            "read": False,
            "type": "version_update",
            "data": {"version": "1.0.0"},
            "workspace": None,
        },
        {
            "id": AnyInt(),
            "sender": {
                "id": user.id,
                "username": user.email,
                "first_name": user.first_name,
                "user_type": "human",
            },
            "created_on": "2021-01-01T12:00:00Z",
            "read": False,
            "type": "fake_application_notification",
            "data": {},
            "workspace": {"id": workspace.id},
        },
    ]


@pytest.mark.django_db
def test_notification_from_identity_includes_sender_type(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace, name="Row writer")
    data_fixture.create_workspace_notification_for_users(
        sender=identity, workspace=workspace, recipients=[user]
    )

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["results"][0]["sender"] == {
        "id": identity.id,
        "username": None,
        "first_name": "Row writer",
        "user_type": "identity",
    }


@pytest.mark.django_db
def test_user_can_mark_notifications_as_read(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    notification = data_fixture.create_workspace_notification_for_users(
        workspace=workspace, recipients=[user]
    )
    recipient = NotificationRecipient.objects.get(
        notification=notification, recipient=user
    )
    assert recipient.read is False

    response = api_client.patch(
        reverse(
            "api:notifications:item",
            kwargs={"workspace_id": workspace.id, "notification_id": notification.id},
        ),
        {"read": True},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["read"] is True


@pytest.mark.django_db
def test_user_cannot_mark_notifications_as_read_if_not_part_of_workspace(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()

    notification = data_fixture.create_workspace_notification_for_users(
        workspace=workspace, recipients=[user]
    )

    response = api_client.patch(
        reverse(
            "api:notifications:item",
            kwargs={"workspace_id": workspace.id, "notification_id": notification.id},
        ),
        {"read": True},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_user_cannot_mark_notifications_as_read_if_notification_does_not_exist(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.patch(
        reverse(
            "api:notifications:item",
            kwargs={"workspace_id": workspace.id, "notification_id": 999},
        ),
        {"read": True},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_NOTIFICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_user_can_mark_all_own_notifications_as_read(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=other_user)

    data_fixture.create_workspace_notification_for_users(
        workspace=workspace, recipients=[user]
    )
    data_fixture.create_user_notification_for_users(recipients=[user])

    # other workspace
    data_fixture.create_workspace_notification_for_users(
        workspace=other_workspace, recipients=[other_user]
    )

    data_fixture.create_broadcast_notification()

    def user_unread_count():
        return NotificationHandler.get_unread_notifications_count(user, workspace)

    def other_user_unread_count():
        return NotificationHandler.get_unread_notifications_count(
            other_user, other_workspace
        )

    assert user_unread_count() == 3
    assert other_user_unread_count() == 2

    response = api_client.post(
        reverse(
            "api:notifications:mark_all_as_read",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    # Only notifications for the user should be marked as read
    assert user_unread_count() == 0
    assert other_user_unread_count() == 2


@pytest.mark.django_db
def test_user_cannot_mark_all_notifications_as_read_if_not_part_of_workspace(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()

    data_fixture.create_workspace_notification_for_users(
        workspace=workspace, recipients=[user]
    )
    data_fixture.create_user_notification_for_users(recipients=[user])

    response = api_client.post(
        reverse(
            "api:notifications:mark_all_as_read",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_user_cannot_mark_all_notifications_as_read_if_workspace_does_not_exist(
    data_fixture, api_client
):
    _, token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse(
            "api:notifications:mark_all_as_read",
            kwargs={"workspace_id": 999},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_user_cannot_clear_all_notifications_if_not_part_of_workspace(
    data_fixture, api_client
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace()

    data_fixture.create_workspace_notification_for_users(
        workspace=workspace, recipients=[user]
    )
    data_fixture.create_user_notification_for_users(recipients=[user])

    response = api_client.delete(
        reverse(
            "api:notifications:list",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"


@pytest.mark.django_db
def test_user_cannot_clear_all_notifications_if_workspace_does_not_exist(
    data_fixture, api_client
):
    _, token = data_fixture.create_user_and_token()

    response = api_client.delete(
        reverse(
            "api:notifications:list",
            kwargs={"workspace_id": 999},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_user_can_clear_all_own_notifications(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    user_2 = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user_2)

    data_fixture.create_workspace_notification_for_users(
        recipients=[user], workspace=workspace
    )
    data_fixture.create_user_notification_for_users(recipients=[user])

    # other workspace and user
    data_fixture.create_workspace_notification_for_users(
        workspace=workspace_2, recipients=[user_2]
    )
    data_fixture.create_user_notification_for_users(recipients=[user_2])

    assert Notification.objects.count() == 4

    response = api_client.delete(
        reverse(
            "api:notifications:list",
            kwargs={"workspace_id": workspace.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert Notification.objects.count() == 2
