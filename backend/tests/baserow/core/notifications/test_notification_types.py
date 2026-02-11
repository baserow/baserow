from unittest.mock import call, patch

from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT

from baserow.core.notification_types import (
    BaserowVersionUpgradeNotificationType,
    WorkspaceInvitationAcceptedNotificationType,
    WorkspaceInvitationCreatedNotificationType,
    WorkspaceInvitationRejectedNotificationType,
)
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
@patch("baserow.core.notifications.signals.notification_created.send")
def test_notification_creation_on_creating_group_invitation(
    mocked_notification_created, api_client, data_fixture
):
    user_1 = data_fixture.create_user(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace_1 = data_fixture.create_workspace(user=user_1)
    workspace_2 = data_fixture.create_workspace(user=user_2)

    with freeze_time("2023-07-06 12:00"):
        token_1 = data_fixture.generate_token(user_1)
        response = api_client.post(
            reverse(
                "api:workspaces:invitations:list",
                kwargs={"workspace_id": workspace_1.id},
            ),
            {
                "email": "test2@test.nl",
                "permissions": "ADMIN",
                "base_url": "http://localhost:3000/invite",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    invitation_id = response_json["id"]

    mocked_notification_created.assert_called_once()
    args = mocked_notification_created.call_args
    assert args == call(
        sender=NotificationHandler,
        notification=NotificationHandler.get_notification_by(
            user_2, data__contains={"invitation_id": invitation_id}
        ),
        notification_recipients=list(
            NotificationRecipient.objects.filter(recipient=user_2)
        ),
        user=user_1,
    )

    # the user can see the notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace_2.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "created_on": "2023-07-06T12:00:00Z",
                "type": WorkspaceInvitationCreatedNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": None,
                "data": {
                    "invitation_id": invitation_id,
                    "invited_to_workspace_id": workspace_1.id,
                    "invited_to_workspace_name": workspace_1.name,
                },
            }
        ],
    }


@pytest.mark.django_db
@patch("baserow.core.notifications.signals.notification_created.send")
def test_notification_creation_on_accepting_group_invitation(
    mocked_notification_created, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2 = data_fixture.create_user(email="test2@test.nl")
    workspace_1 = data_fixture.create_workspace(user=user_1)
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email=user_2.email,
        permissions="ADMIN",
    )

    with freeze_time("2023-07-06 12:00"):
        token_2 = data_fixture.generate_token(user_2)
        response = api_client.post(
            reverse(
                "api:workspaces:invitations:accept",
                kwargs={"workspace_invitation_id": invitation.id},
            ),
            HTTP_AUTHORIZATION=f"JWT {token_2}",
        )

    assert response.status_code == HTTP_200_OK

    mocked_notification_created.assert_called_once()
    args = mocked_notification_created.call_args
    assert args == call(
        sender=NotificationHandler,
        notification=NotificationHandler.get_notification_by(
            user_1, data__contains={"invitation_id": invitation.id}
        ),
        notification_recipients=list(
            NotificationRecipient.objects.filter(recipient=user_1)
        ),
        user=user_2,
    )

    # the user can see the notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "created_on": "2023-07-06T12:00:00Z",
                "type": WorkspaceInvitationAcceptedNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_2.id,
                    "username": user_2.username,
                    "first_name": user_2.first_name,
                },
                "workspace": {"id": workspace_1.id},
                "data": {
                    "invitation_id": invitation.id,
                    "invited_to_workspace_id": workspace_1.id,
                    "invited_to_workspace_name": workspace_1.name,
                },
            }
        ],
    }


@pytest.mark.django_db
@patch("baserow.core.notifications.signals.notification_created.send")
def test_notification_creation_on_rejecting_group_invitation(
    mocked_notification_created, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2 = data_fixture.create_user(email="test2@test.nl")
    workspace_1 = data_fixture.create_workspace(user=user_1)
    invitation = data_fixture.create_workspace_invitation(
        invited_by=user_1,
        workspace=workspace_1,
        email=user_2.email,
        permissions="ADMIN",
    )

    with freeze_time("2023-07-06 12:00"):
        token_2 = data_fixture.generate_token(user_2)
        response = api_client.post(
            reverse(
                "api:workspaces:invitations:reject",
                kwargs={"workspace_invitation_id": invitation.id},
            ),
            HTTP_AUTHORIZATION=f"JWT {token_2}",
        )

    assert response.status_code == HTTP_204_NO_CONTENT

    mocked_notification_created.assert_called_once()
    args = mocked_notification_created.call_args
    assert args == call(
        sender=NotificationHandler,
        notification=NotificationHandler.get_notification_by(
            user_1,
            data__contains={"invitation_id": invitation.id},
        ),
        notification_recipients=list(
            NotificationRecipient.objects.filter(recipient=user_1)
        ),
        user=user_2,
    )

    # the user can see the notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "created_on": "2023-07-06T12:00:00Z",
                "type": WorkspaceInvitationRejectedNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_2.id,
                    "username": user_2.username,
                    "first_name": user_2.first_name,
                },
                "workspace": {"id": workspace_1.id},
                "data": {
                    "invitation_id": invitation.id,
                    "invited_to_workspace_id": workspace_1.id,
                    "invited_to_workspace_name": workspace_1.name,
                },
            }
        ],
    }


@pytest.mark.django_db
@patch("baserow.core.notifications.signals.notification_created.send")
def test_baserow_version_upgrade_is_sent_as_broadcast_notification(
    mocked_notification_created, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token()
    user_2, token_2 = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(user=user_1)
    workspace_2 = data_fixture.create_workspace(user=user_2)

    with freeze_time("2023-07-06 12:00"):
        BaserowVersionUpgradeNotificationType.create_version_upgrade_broadcast_notification(
            "1.19", "/blog/release-notes/1.19"
        )

    mocked_notification_created.assert_called_once()
    args = mocked_notification_created.call_args
    notification = NotificationHandler.get_notification_by(user_1, broadcast=True)
    assert args == call(
        sender=NotificationHandler,
        notification=notification,
        notification_recipients=list(
            NotificationRecipient.objects.filter(
                recipient=None, notification=notification
            )
        ),
        user=None,
    )

    excepted_response = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "created_on": "2023-07-06T12:00:00Z",
                "type": BaserowVersionUpgradeNotificationType.type,
                "data": {
                    "version": "1.19",
                    "release_notes_url": "/blog/release-notes/1.19",
                },
                "read": False,
                "sender": None,
                "workspace": None,
            }
        ],
    }

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace_1.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == excepted_response

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace_2.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == excepted_response
