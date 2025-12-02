from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.notification_types import (
    FormSubmittedNotificationType,
)
from baserow.core.models import WorkspaceUser
from baserow.test_utils.helpers import AnyInt, setup_interesting_test_table


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_user_receive_notification_on_form_submit(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1, token_1 = data_fixture.create_user_and_token(email="test1@test.nl")
    user_2, token_2 = data_fixture.create_user_and_token(email="test2@test.nl")

    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    text_field = data_fixture.create_text_field(name="text", table=table)
    number_field = data_fixture.create_number_field(name="number", table=table)

    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=False, enabled=True, order=2
    )

    def submit_form():
        response = api_client.post(
            reverse("api:database:views:form:submit", kwargs={"slug": form.slug}),
            {
                f"field_{text_field.id}": "Valid",
                f"field_{number_field.id}": 0,
            },
            format="json",
        )
        assert response.status_code == HTTP_200_OK
        return response

    # by default no users are notified on form submit
    submit_form()
    assert mocked_broadcast_to_users.call_count == 0

    # Set the form to notify user_1 on submit
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": form.id}),
        {"receive_notification_on_submit": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    assert form.users_to_notify_on_submit.count() == 1

    # now user_1 should receive the notification
    with freeze_time("2021-01-01 12:00"):
        submit_form()

    expected_notification = {
        "id": AnyInt(),
        "type": "form_submitted",
        "sender": None,
        "workspace": {"id": workspace.id},
        "created_on": "2021-01-01T12:00:00Z",
        "read": False,
        "data": {
            "row_id": AnyInt(),
            "form_id": form.id,
            "form_name": form.name,
            "table_id": table.id,
            "table_name": table.name,
            "database_id": database.id,
            "values": [
                ["text", "Valid"],
                ["number", "0"],
            ],
        },
    }

    # the notification can be retrieved via the api and received via websockets
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK

    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [expected_notification],
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert args[0] == [
        [user_1.id],
        {
            "type": "notifications_created",
            "notifications": [expected_notification],
        },
    ]

    # user_2 received nothing
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_all_interested_users_receive_the_notification_on_form_submit(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1 = data_fixture.create_user(email="test1@test.nl")
    user_2 = data_fixture.create_user(email="test2@test.nl")
    user_3 = data_fixture.create_user(email="test3@test.nl")
    user_4 = data_fixture.create_user(email="test4@test.nl")

    workspace = data_fixture.create_workspace(members=[user_1, user_2, user_3, user_4])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    text_field = data_fixture.create_text_field(name="text", table=table)
    number_field = data_fixture.create_number_field(name="number", table=table)

    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=False, enabled=True, order=2
    )

    form.users_to_notify_on_submit.add(user_1, user_2, user_3, user_4)

    def submit_form():
        response = api_client.post(
            reverse("api:database:views:form:submit", kwargs={"slug": form.slug}),
            {
                f"field_{text_field.id}": "Valid",
                f"field_{number_field.id}": 0,
            },
            format="json",
        )
        assert response.status_code == HTTP_200_OK
        return response

    submit_form()

    # all the user will receive the notification
    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert unordered(args[0][0], [user_1.id, user_2.id, user_3.id, user_4.id])


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_only_users_with_access_to_the_table_receive_the_notification_on_form_submit(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user_1 = data_fixture.create_user(email="test1@test.nl")
    user_2 = data_fixture.create_user(email="test2@test.nl")

    workspace = data_fixture.create_workspace(members=[user_1, user_2])
    database = data_fixture.create_database_application(
        user=user_1, workspace=workspace
    )
    table = data_fixture.create_database_table(name="Example", database=database)
    text_field = data_fixture.create_text_field(name="text", table=table)
    number_field = data_fixture.create_number_field(name="number", table=table)

    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=False, enabled=True, order=2
    )

    form.users_to_notify_on_submit.add(user_1, user_2)

    def submit_form():
        response = api_client.post(
            reverse("api:database:views:form:submit", kwargs={"slug": form.slug}),
            {
                f"field_{text_field.id}": "Valid",
                f"field_{number_field.id}": 0,
            },
            format="json",
        )
        assert response.status_code == HTTP_200_OK
        return response

    submit_form()

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert unordered(args[0][0], [user_1.id, user_2.id])

    mocked_broadcast_to_users.reset_mock()

    # user_2 should not receive the notification because he has no access to the table
    WorkspaceUser.objects.filter(
        user__in=[user_1, user_2], workspace=workspace
    ).delete()

    submit_form()

    assert mocked_broadcast_to_users.call_count == 0

    # If a user regain access to the table, he should receive the notification again
    WorkspaceUser.objects.create(user=user_1, workspace=workspace, order=1)

    submit_form()

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert args[0][0] == [user_1.id]


@pytest.mark.django_db(transaction=True)
def test_form_submit_notification_can_be_render_as_email(api_client, data_fixture):
    user = data_fixture.create_user()

    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(name="Example", database=database)
    text_field = data_fixture.create_text_field(name="text", table=table)
    number_field = data_fixture.create_number_field(name="number", table=table)

    form = data_fixture.create_form_view(table=table, public=True)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    data_fixture.create_form_view_field_option(
        form, number_field, required=False, enabled=True, order=2
    )

    form_values = {f"field_{text_field.id}": "Valid", f"field_{number_field.id}": 0}
    row = ViewHandler().submit_form_view(user, form, form_values)

    notification_recipients = (
        FormSubmittedNotificationType.create_form_submitted_notification(
            form, row, form_values, [user]
        )
    )
    notification = notification_recipients[0].notification

    assert FormSubmittedNotificationType.get_notification_title_for_email(
        notification, {}
    ) == "%(form_name)s has been submitted in %(table_name)s" % {
        "form_name": notification.data["form_name"],
        "table_name": notification.data["table_name"],
    }

    assert (
        FormSubmittedNotificationType.get_notification_description_for_email(
            notification, {}
        )
        == "text: Valid\n\nnumber: 0"
    )

    # Add two more fields to the form
    text_field_2 = data_fixture.create_text_field(name="text 2", table=table)
    number_field_2 = data_fixture.create_number_field(name="number 2", table=table)
    data_fixture.create_form_view_field_option(
        form, text_field_2, required=True, enabled=True, order=3
    )
    data_fixture.create_form_view_field_option(
        form, number_field_2, required=False, enabled=True, order=4
    )

    form_values = {
        f"field_{text_field.id}": "Valid",
        f"field_{number_field.id}": 0,
        f"field_{text_field_2.id}": "Valid 2",
        f"field_{number_field_2.id}": 0,
    }
    row = ViewHandler().submit_form_view(user, form, form_values)

    notification_recipients = (
        FormSubmittedNotificationType.create_form_submitted_notification(
            form, row, form_values, [user]
        )
    )
    notification = notification_recipients[0].notification

    assert FormSubmittedNotificationType.get_notification_title_for_email(
        notification, {}
    ) == "%(form_name)s has been submitted in %(table_name)s" % {
        "form_name": notification.data["form_name"],
        "table_name": notification.data["table_name"],
    }

    assert (
        FormSubmittedNotificationType.get_notification_description_for_email(
            notification, {}
        )
        == "text: Valid\n\nnumber: 0\n\ntext 2: Valid 2\n\n\nand 1 more field"
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_can_user_receive_notification_for_all_interesting_field_values(
    mocked_broadcast_to_users, api_client, data_fixture
):
    user = data_fixture.create_user()

    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table, user, row, _, _ = setup_interesting_test_table(
        data_fixture, user, database=database
    )

    form = data_fixture.create_form_view(table=table, public=True)
    form.users_to_notify_on_submit.add(user)

    model = table.get_model()
    form_values = {}
    expected_values = []

    for i, field_object in enumerate(model.get_field_objects(), start=1):
        field_instance = field_object["field"]
        field_type = field_object["type"]
        field_name = field_object["name"]
        if field_object["type"].can_be_in_form_view:
            data_fixture.create_form_view_field_option(
                form, field_instance, required=True, enabled=True, order=i
            )
            input_value = field_type.serialize_to_input_value(
                field_instance, getattr(row, field_name)
            )
            form_values[field_name] = input_value
            human_readable_value = field_type.get_human_readable_value(
                getattr(row, field_name), field_object
            )
            expected_values.append([field_instance.name, human_readable_value])

    row = ViewHandler().submit_form_view(None, form, form_values)
    assert row is not None
    assert mocked_broadcast_to_users.call_count == 1
    notification = mocked_broadcast_to_users.call_args[0][0][1]["notifications"][0]
    assert notification["data"]["values"] == expected_values
