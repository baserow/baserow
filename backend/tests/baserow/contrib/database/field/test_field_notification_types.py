from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

from django.db import transaction
from django.db.models import Q
from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.fields.notification_types import (
    CollaboratorAddedToRowNotificationType,
    UserMentionInRichTextFieldNotificationType,
)
from baserow.contrib.database.rows.actions import (
    CreateRowActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import RichTextFieldMention
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import (
    AnyInt,
    AnyStr,
    assert_undo_redo_actions_are_valid,
)

pytestmark = pytest.mark.enable_signals(
    "baserow.core.notifications.tasks.send_queued_notifications_to_users.delay",
    "baserow.ws.tasks.broadcast_to_users.delay",
)


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notification_creation_on_adding_users_on_collaborator_fields(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    user_3, token_3 = data_fixture.create_user_and_token(email="test3@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2, user_3])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user_1, table=table, name="Collaborator 1", notify_user_when_added=True
    )
    row = RowHandler().create_row(
        user=user_1, table=table, values={collaborator_field.id: []}
    )

    with freeze_time("2023-07-06 12:00"):
        token_1 = data_fixture.generate_token(user_1)
        response = api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            ),
            {f"field_{collaborator_field.id}": [{"id": user_2.id}]},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_200_OK

    # user_2 can see his own notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
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
                "type": CollaboratorAddedToRowNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": {"id": workspace.id},
                "data": {
                    "row_id": row.id,
                    "row_name": str(row),
                    "field_id": collaborator_field.id,
                    "field_name": collaborator_field.name,
                    "table_id": table.id,
                    "table_name": table.name,
                    "database_id": database.id,
                    "database_name": database.name,
                },
            }
        ],
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": [
                {
                    "id": AnyInt(),
                    "type": CollaboratorAddedToRowNotificationType.type,
                    "sender": {
                        "id": user_1.id,
                        "username": user_1.username,
                        "first_name": user_1.first_name,
                    },
                    "created_on": "2023-07-06T12:00:00Z",
                    "data": {
                        "row_id": row.id,
                        "row_name": str(row),
                        "field_id": collaborator_field.id,
                        "field_name": collaborator_field.name,
                        "table_id": table.id,
                        "table_name": table.name,
                        "database_id": database.id,
                        "database_name": database.name,
                    },
                    "workspace": {"id": workspace.id},
                    "read": False,
                }
            ],
        },
    )

    # user_3 has no notifications yet
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {"count": 0, "next": None, "previous": None, "results": []}

    # Adding user_3 to the list of collaborators only notify user_3
    with freeze_time("2023-07-06 12:00"):
        response = api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            ),
            {
                f"field_{collaborator_field.id}": [
                    {"id": user_2.id},
                    {"id": user_3.id},
                ]
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_200_OK

    assert mocked_broadcast_to_users.call_count == 2
    args = mocked_broadcast_to_users.call_args_list
    assert args[1][0] == call(
        [user_3.id],
        {
            "type": "notifications_created",
            "notifications": [
                {
                    "id": AnyInt(),
                    "type": CollaboratorAddedToRowNotificationType.type,
                    "sender": {
                        "id": user_1.id,
                        "username": user_1.username,
                        "first_name": user_1.first_name,
                    },
                    "created_on": "2023-07-06T12:00:00Z",
                    "data": {
                        "row_id": row.id,
                        "row_name": str(row),
                        "field_id": collaborator_field.id,
                        "field_name": collaborator_field.name,
                        "table_id": table.id,
                        "table_name": table.name,
                        "database_id": database.id,
                        "database_name": database.name,
                    },
                    "workspace": {"id": workspace.id},
                    "read": False,
                }
            ],
        },
    )

    # user_3 list notifications and see there is a new one for him
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_3}",
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
                "type": CollaboratorAddedToRowNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": {"id": workspace.id},
                "data": {
                    "row_id": row.id,
                    "row_name": str(row),
                    "field_id": collaborator_field.id,
                    "field_name": collaborator_field.name,
                    "table_id": table.id,
                    "table_name": table.name,
                    "database_id": database.id,
                    "database_name": database.name,
                },
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notifications_are_grouped_when_user_is_added_to_multiple_rows(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace
    )
    table = data_fixture.create_database_table(database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user_1, table=table, notify_user_when_added=True
    )

    with freeze_time("2023-07-06 12:00"):
        token_1 = data_fixture.generate_token(user_1)
        url = reverse("api:database:rows:batch", kwargs={"table_id": table.id})
        request_body = {
            "items": [
                {f"field_{collaborator_field.id}": [{"id": user_2.id}]},
                {f"field_{collaborator_field.id}": [{"id": user_2.id}]},
            ]
        }
        response = api_client.post(
            url,
            request_body,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_200_OK
        row_1_id = response.json()["items"][0]["id"]
        row_2_id = response.json()["items"][1]["id"]

    # user_2 can see his own notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "created_on": "2023-07-06T12:00:00Z",
                "type": CollaboratorAddedToRowNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": {"id": workspace.id},
                "data": {
                    "row_id": row_1_id,
                    "row_name": f"unnamed row {row_1_id}",
                    "field_id": collaborator_field.id,
                    "field_name": collaborator_field.name,
                    "table_id": table.id,
                    "table_name": table.name,
                    "database_id": database.id,
                    "database_name": database.name,
                },
            },
            {
                "id": AnyInt(),
                "created_on": "2023-07-06T12:00:00Z",
                "type": CollaboratorAddedToRowNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": {"id": workspace.id},
                "data": {
                    "row_id": row_2_id,
                    "row_name": f"unnamed row {row_2_id}",
                    "field_id": collaborator_field.id,
                    "field_name": collaborator_field.name,
                    "table_id": table.id,
                    "table_name": table.name,
                    "database_id": database.id,
                    "database_name": database.name,
                },
            },
        ],
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": [
                {
                    "id": AnyInt(),
                    "type": CollaboratorAddedToRowNotificationType.type,
                    "sender": {
                        "id": user_1.id,
                        "username": user_1.username,
                        "first_name": user_1.first_name,
                    },
                    "created_on": "2023-07-06T12:00:00Z",
                    "data": {
                        "row_id": row_1_id,
                        "row_name": f"unnamed row {row_1_id}",
                        "field_id": collaborator_field.id,
                        "field_name": collaborator_field.name,
                        "table_id": table.id,
                        "table_name": table.name,
                        "database_id": database.id,
                        "database_name": database.name,
                    },
                    "workspace": {"id": workspace.id},
                    "read": False,
                },
                {
                    "id": AnyInt(),
                    "type": CollaboratorAddedToRowNotificationType.type,
                    "sender": {
                        "id": user_1.id,
                        "username": user_1.username,
                        "first_name": user_1.first_name,
                    },
                    "created_on": "2023-07-06T12:00:00Z",
                    "data": {
                        "row_id": row_2_id,
                        "row_name": f"unnamed row {row_2_id}",
                        "field_id": collaborator_field.id,
                        "field_name": collaborator_field.name,
                        "table_id": table.id,
                        "table_name": table.name,
                        "database_id": database.id,
                        "database_name": database.name,
                    },
                    "workspace": {"id": workspace.id},
                    "read": False,
                },
            ],
        },
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notifications_are_not_created_if_the_field_parameter_is_false(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user_1, table=table, name="Collaborator 1", notify_user_when_added=False
    )
    row = RowHandler().create_row(
        user=user_1, table=table, values={collaborator_field.id: []}
    )

    with freeze_time("2023-07-06 12:00"):
        token_1 = data_fixture.generate_token(user_1)
        response = api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            ),
            {f"field_{collaborator_field.id}": [{"id": user_1.id}, {"id": user_2.id}]},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_200_OK

    # user_2 can see his own notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }

    assert mocked_broadcast_to_users.call_count == 0


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_email_notifications_are_created_correctly_for_collaborators_added(
    mock_get_mail_connection,
    data_fixture,
    api_client,
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    user_1, token_1 = data_fixture.create_user_and_token(
        email="test1@test.nl", first_name="User 1"
    )
    user_2 = data_fixture.create_user(email="test2@test.nl", first_name="User 2")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user_1, table=table, name="Collaborator 1", notify_user_when_added=True
    )
    row = RowHandler().create_row(
        user=user_1, table=table, values={collaborator_field.id: []}
    )

    with freeze_time("2023-07-06 12:00"):
        token_1 = data_fixture.generate_token(user_1)
        response = api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            ),
            {f"field_{collaborator_field.id}": [{"id": user_2.id}]},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_200_OK

    # Force to send the notifications
    res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
        Q(pk=user_2.pk)
    )
    assert res.users_with_notifications == [user_2]
    assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
    assert res.users_with_notifications[0].total_unsent_count == 1
    assert res.remaining_users_to_notify_count == 0

    mock_get_mail_connection.assert_called_once_with(fail_silently=False)
    summary_emails = mock_connection.send_messages.call_args[0][0]
    assert len(summary_emails) == 1
    user_2_summary_email = summary_emails[0]
    assert user_2_summary_email.to == [user_2.email]
    assert user_2_summary_email.get_subject() == "You have 1 new notification - Baserow"

    notif = NotificationRecipient.objects.get(recipient=user_2)
    notification_url = f"http://localhost:3000/notification/{notif.workspace_id}/{notif.notification_id}"

    expected_context = {
        "notifications": [
            {
                "title": f"User 1 assigned you to Collaborator 1 in row unnamed row"
                f" {row.id} in Example.",
                "description": None,
                "url": notification_url,
            }
        ],
        "new_notifications_count": 1,
        "unlisted_notifications_count": 0,
    }
    user_2_summary_email_context = user_2_summary_email.get_context()

    for k, v in expected_context.items():
        assert user_2_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notification_creation_when_mentioning_users_in_a_rich_text_field_on_row_create(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, _ = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    rich_text_field = data_fixture.create_long_text_field(
        user=user_1, table=table, name="RichTextField", long_text_enable_rich_text=True
    )

    assert RichTextFieldMention.objects.count() == 0

    with transaction.atomic(), freeze_time("2023-07-06 12:00"):
        row = RowHandler().create_row(
            user=user_1,
            table=table,
            values={rich_text_field.db_column: f"Hello @{user_2.id}"},
        )

    # Ensure the mention is created in the apposite table
    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # user_2 can see his own notification in the list of notifications
    expected_payload = [
        {
            "id": AnyInt(),
            "created_on": "2023-07-06T12:00:00Z",
            "type": UserMentionInRichTextFieldNotificationType.type,
            "read": False,
            "sender": {
                "id": user_1.id,
                "username": user_1.username,
                "first_name": user_1.first_name,
            },
            "workspace": {"id": workspace.id},
            "data": {
                "row_id": row.id,
                "row_name": str(row),
                "field_id": rich_text_field.id,
                "field_name": rich_text_field.name,
                "table_id": table.id,
                "table_name": table.name,
                "database_id": database.id,
                "database_name": database.name,
            },
        }
    ]
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": expected_payload,
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": expected_payload,
        },
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notification_creation_when_mentioning_users_in_a_rich_text_field_on_row_update(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, _ = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    rich_text_field = data_fixture.create_long_text_field(
        user=user_1, table=table, name="RichTextField", long_text_enable_rich_text=True
    )
    model = table.get_model()

    assert RichTextFieldMention.objects.count() == 0

    with transaction.atomic(), freeze_time("2023-07-06 12:00"):
        row = RowHandler().create_row(
            user=user_1,
            table=table,
            values={rich_text_field.db_column: "Hello!"},
            model=model,
        )

        assert RichTextFieldMention.objects.count() == 0

        RowHandler().update_rows(
            user=user_1,
            table=table,
            rows_values=[
                {"id": row.id, rich_text_field.db_column: f"Hello @{user_2.id}"}
            ],
            model=model,
        )

    # Ensure the mention is created in the apposite table
    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # user_2 can see his own notification in the list of notifications
    expected_payload = [
        {
            "id": AnyInt(),
            "created_on": "2023-07-06T12:00:00Z",
            "type": UserMentionInRichTextFieldNotificationType.type,
            "read": False,
            "sender": {
                "id": user_1.id,
                "username": user_1.username,
                "first_name": user_1.first_name,
            },
            "workspace": {"id": workspace.id},
            "data": {
                "row_id": row.id,
                "row_name": str(row),
                "field_id": rich_text_field.id,
                "field_name": rich_text_field.name,
                "table_id": table.id,
                "table_name": table.name,
                "database_id": database.id,
                "database_name": database.name,
            },
        }
    ]
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": expected_payload,
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": expected_payload,
        },
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notifications_are_not_sent_twice_on_undo_redo_row_create(
    mocked_broadcast_to_users, api_client, data_fixture
):
    session_id = "session-id"
    user_1, _ = data_fixture.create_user_and_token(
        email="test1@test.nl", session_id=session_id
    )
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    rich_text_field = data_fixture.create_long_text_field(
        user=user_1, table=table, name="RichTextField", long_text_enable_rich_text=True
    )
    model = table.get_model()

    assert RichTextFieldMention.objects.count() == 0

    with transaction.atomic(), freeze_time("2023-07-06 12:00"):
        row = action_type_registry.get_by_type(CreateRowActionType).do(
            user=user_1,
            table=table,
            values={rich_text_field.db_column: f"Hello @{user_2.id}!"},
            model=model,
        )

    # Ensure the mention is created in the apposite table
    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # user_2 can see his own notification in the list of notifications
    expected_payload = [
        {
            "id": AnyInt(),
            "created_on": "2023-07-06T12:00:00Z",
            "type": UserMentionInRichTextFieldNotificationType.type,
            "read": False,
            "sender": {
                "id": user_1.id,
                "username": user_1.username,
                "first_name": user_1.first_name,
            },
            "workspace": {"id": workspace.id},
            "data": {
                "row_id": row.id,
                "row_name": str(row),
                "field_id": rich_text_field.id,
                "field_name": rich_text_field.name,
                "table_id": table.id,
                "table_name": table.name,
                "database_id": database.id,
                "database_name": database.name,
            },
        }
    ]
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": expected_payload,
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": expected_payload,
        },
    )

    # clear all the notifications
    NotificationHandler.clear_all_notifications(user_2, workspace)
    mocked_broadcast_to_users.reset_mock()

    undo_time = datetime(2023, 7, 6, 12, 10, tzinfo=timezone.utc)
    with transaction.atomic(), freeze_time(undo_time):
        action_undone = ActionHandler.undo(
            user_1, [TableActionScopeType.value(table_id=table.id)], session_id
        )
    assert_undo_redo_actions_are_valid(action_undone, [CreateRowActionType])

    # The mention is still there because it's deleted only when the row is perm deleted.
    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # Because the mention is there, if we redo the action, the notification should not
    # be sent again, but the mention should be unmarked for deletion
    redo_time = datetime(2023, 7, 6, 12, 20, tzinfo=timezone.utc)
    with transaction.atomic(), freeze_time(redo_time):
        action_undone = ActionHandler.redo(
            user_1, [TableActionScopeType.value(table_id=table.id)], session_id
        )
    assert_undo_redo_actions_are_valid(action_undone, [CreateRowActionType])

    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # No notification should be created/sent
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {"count": 0, "next": None, "previous": None, "results": []}
    assert mocked_broadcast_to_users.call_count == 0

    # If we perm delete the row, the mention should be deleted and the next time the
    # notification should be sent again
    TrashHandler.trash(user_1, workspace, database, row)
    TrashHandler.permanently_delete(row, table.id)
    assert RichTextFieldMention.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notifications_are_not_sent_twice_on_undo_redo_row_update(
    mocked_broadcast_to_users, api_client, data_fixture
):
    session_id = "session-id"
    user_1, _ = data_fixture.create_user_and_token(
        email="test1@test.nl", session_id=session_id
    )
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    rich_text_field = data_fixture.create_long_text_field(
        user=user_1, table=table, name="RichTextField", long_text_enable_rich_text=True
    )
    model = table.get_model()

    assert RichTextFieldMention.objects.count() == 0

    with transaction.atomic(), freeze_time("2023-07-06 12:00"):
        row = RowHandler().create_row(user=user_1, table=table, model=model)
        (row,) = (
            action_type_registry.get_by_type(UpdateRowsActionType)
            .do(
                user=user_1,
                table=table,
                rows_values=[
                    {"id": row.id, rich_text_field.db_column: f"Hello @{user_2.id}!"}
                ],
                model=model,
            )
            .updated_rows
        )

    # Ensure the mention is created in the apposite table
    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # user_2 can see his own notification in the list of notifications
    expected_payload = [
        {
            "id": AnyInt(),
            "created_on": "2023-07-06T12:00:00Z",
            "type": UserMentionInRichTextFieldNotificationType.type,
            "read": False,
            "sender": {
                "id": user_1.id,
                "username": user_1.username,
                "first_name": user_1.first_name,
            },
            "workspace": {"id": workspace.id},
            "data": {
                "row_id": row.id,
                "row_name": str(row),
                "field_id": rich_text_field.id,
                "field_name": rich_text_field.name,
                "table_id": table.id,
                "table_name": table.name,
                "database_id": database.id,
                "database_name": database.name,
            },
        }
    ]
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": expected_payload,
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": expected_payload,
        },
    )

    # clear all the notifications
    NotificationHandler.clear_all_notifications(user_2, workspace)
    mocked_broadcast_to_users.reset_mock()

    undo_time = datetime(2023, 7, 6, 12, 10, tzinfo=timezone.utc)
    with transaction.atomic(), freeze_time(undo_time):
        action_undone = ActionHandler.undo(
            user_1, [TableActionScopeType.value(table_id=table.id)], session_id
        )
    assert_undo_redo_actions_are_valid(action_undone, [UpdateRowsActionType])

    # The mention is still there because it's deleted only when the row is perm deleted.
    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at == undo_time

    # Because the mention is there, if we redo the action, the notification should not
    # be sent again, but the mention should be unmarked for deletion
    redo_time = datetime(2023, 7, 6, 12, 20, tzinfo=timezone.utc)
    with transaction.atomic(), freeze_time(redo_time):
        action_undone = ActionHandler.redo(
            user_1, [TableActionScopeType.value(table_id=table.id)], session_id
        )
    assert_undo_redo_actions_are_valid(action_undone, [UpdateRowsActionType])

    mentions = RichTextFieldMention.objects.all()
    assert len(mentions) == 1
    assert mentions[0].row_id == row.id
    assert mentions[0].field_id == rich_text_field.id
    assert mentions[0].user_id == user_2.id
    assert mentions[0].marked_for_deletion_at is None

    # No notification should be created/sent
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_notification_are_not_sent_to_users_outside_workspace(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, _ = data_fixture.create_user_and_token(email="test1@test.nl")
    ext_user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(user=user_1)
    workspace_2 = data_fixture.create_workspace(user=ext_user_2)
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    rich_text_field = data_fixture.create_long_text_field(
        user=user_1, table=table, name="RichTextField", long_text_enable_rich_text=True
    )

    assert RichTextFieldMention.objects.count() == 0

    with transaction.atomic(), freeze_time("2023-07-06 12:00"):
        RowHandler().create_row(
            user=user_1,
            table=table,
            values={rich_text_field.db_column: f"Hello @{ext_user_2.id}"},
        )

    assert RichTextFieldMention.objects.count() == 0
    assert NotificationRecipient.objects.count() == 0

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace_2.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_email_notifications_are_created_correctly_for_mentions_in_rich_text_field(
    mock_get_mail_connection, data_fixture
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    user_1, _ = data_fixture.create_user_and_token(
        first_name="Lisa Smith", email="test1@test.nl"
    )
    user_2, _ = data_fixture.create_user_and_token(email="test2@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Placeholder"
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    rich_text_field = data_fixture.create_long_text_field(
        user=user_1, table=table, name="RichTextField", long_text_enable_rich_text=True
    )
    model = table.get_model()

    assert RichTextFieldMention.objects.count() == 0

    with transaction.atomic(), freeze_time("2023-07-06 12:00"):
        row = RowHandler().create_row(
            user=user_1,
            table=table,
            values={rich_text_field.db_column: f"Hello, @{user_2.id}"},
            model=model,
        )

    # Force to send the notifications
    res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
        Q(pk=user_2.pk)
    )
    assert res.users_with_notifications == [user_2]
    assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
    assert res.users_with_notifications[0].total_unsent_count == 1
    assert res.remaining_users_to_notify_count == 0

    mock_get_mail_connection.assert_called_once_with(fail_silently=False)
    summary_emails = mock_connection.send_messages.call_args[0][0]
    assert len(summary_emails) == 1
    user_2_summary_email = summary_emails[0]
    assert user_2_summary_email.to == [user_2.email]
    assert user_2_summary_email.get_subject() == "You have 1 new notification - Baserow"

    notif = NotificationRecipient.objects.get(recipient=user_2)
    notification_url = f"http://localhost:3000/notification/{notif.workspace_id}/{notif.notification_id}"

    expected_context = {
        "notifications": [
            {
                "title": (
                    f"Lisa Smith mentioned you in RichTextField in row unnamed row {row.id} in Example."
                ),
                "description": None,
                "url": notification_url,
            }
        ],
        "new_notifications_count": 1,
        "unlisted_notifications_count": 0,
    }
    user_2_summary_email_context = user_2_summary_email.get_context()

    for k, v in expected_context.items():
        assert user_2_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
def test_anonymous_user_can_send_collaborator_notification_via_public_form(
    mocked_broadcast_to_users, api_client, data_fixture
):
    """Test that anonymous users can trigger CollaboratorAddedToRowNotificationType via
    public form submission."""

    user_1, token_1 = data_fixture.create_user_and_token(email="owner@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="collaborator@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Test Database"
    )
    table = data_fixture.create_database_table(name="Test Table", database=database)

    # Create a collaborator field with notifications enabled
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user_1, table=table, name="Assignees", notify_user_when_added=True
    )

    # Create a public form view
    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(
        form, collaborator_field, required=False, enabled=True, order=1
    )

    with freeze_time("2023-07-06 12:00"):
        # Submit form as anonymous user (no authentication token)
        url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
        response = api_client.post(
            url,
            {f"field_{collaborator_field.id}": [{"id": user_2.id}]},
            format="json",
            # No HTTP_AUTHORIZATION header - anonymous submission
        )
        assert response.status_code == HTTP_200_OK

    # Verify that user_2 received a notification
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1

    notification = response_json["results"][0]
    assert notification["type"] == CollaboratorAddedToRowNotificationType.type
    assert notification["sender"] is None  # Anonymous user, so no sender
    assert notification["data"]["field_id"] == collaborator_field.id
    assert notification["data"]["field_name"] == collaborator_field.name
    assert notification["data"]["table_id"] == table.id
    assert notification["data"]["table_name"] == table.name
    assert notification["data"]["database_id"] == database.id
    assert notification["data"]["database_name"] == database.name

    # Verify WebSocket notification was sent
    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user_2.id],
        {
            "type": "notifications_created",
            "notifications": [
                {
                    "id": AnyInt(),
                    "type": CollaboratorAddedToRowNotificationType.type,
                    "sender": None,  # Anonymous submission
                    "created_on": "2023-07-06T12:00:00Z",
                    "data": {
                        "row_id": AnyInt(),
                        "row_name": AnyStr(),
                        "field_id": collaborator_field.id,
                        "field_name": collaborator_field.name,
                        "table_id": table.id,
                        "table_name": table.name,
                        "database_id": database.id,
                        "database_name": database.name,
                    },
                    "workspace": {"id": workspace.id},
                    "read": False,
                }
            ],
        },
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_email_notifications_show_unknown_user_for_anonymous_form_submissions(
    mock_get_mail_connection, api_client, data_fixture
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    user_1, _ = data_fixture.create_user_and_token(email="owner@test.nl")
    user_2, _ = data_fixture.create_user_and_token(email="collaborator@test.nl")
    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace, name="Test Database"
    )
    table = data_fixture.create_database_table(name="Test Table", database=database)

    # Create a collaborator field with notifications enabled
    collaborator_field = data_fixture.create_multiple_collaborators_field(
        user=user_1, table=table, name="Assignees", notify_user_when_added=True
    )

    # Create a public form view
    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(
        form, collaborator_field, required=False, enabled=True, order=1
    )

    with freeze_time("2023-07-06 12:00"):
        # Submit form as anonymous user (no authentication token)
        url = reverse("api:database:views:form:submit", kwargs={"slug": form.slug})
        response = api_client.post(
            url,
            {f"field_{collaborator_field.id}": [{"id": user_2.id}]},
            format="json",
            # No HTTP_AUTHORIZATION header - anonymous submission
        )
        assert response.status_code == HTTP_200_OK
        created_row_id = response.json()["row_id"]

    # Force to send the notifications
    res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
        Q(pk=user_2.pk)
    )
    assert res.users_with_notifications == [user_2]
    assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
    assert res.users_with_notifications[0].total_unsent_count == 1
    assert res.remaining_users_to_notify_count == 0

    mock_get_mail_connection.assert_called_once_with(fail_silently=False)
    summary_emails = mock_connection.send_messages.call_args[0][0]
    assert len(summary_emails) == 1
    user_2_summary_email = summary_emails[0]
    assert user_2_summary_email.to == [user_2.email]
    assert user_2_summary_email.get_subject() == "You have 1 new notification - Baserow"

    notif = NotificationRecipient.objects.get(recipient=user_2)
    notification_url = f"http://localhost:3000/notification/{notif.workspace_id}/{notif.notification_id}"

    # Verify that the email title shows "An unknown user" for anonymous submissions
    expected_context = {
        "notifications": [
            {
                "title": (
                    f"An unknown user assigned you to Assignees in row unnamed row {created_row_id} in Test Table."
                ),
                "description": None,
                "url": notification_url,
            }
        ],
        "new_notifications_count": 1,
        "unlisted_notifications_count": 0,
    }
    user_2_summary_email_context = user_2_summary_email.get_context()

    for k, v in expected_context.items():
        assert user_2_summary_email_context[k] == v
