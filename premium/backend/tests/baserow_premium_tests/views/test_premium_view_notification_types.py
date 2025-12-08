from unittest.mock import patch

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_user_stop_receiving_notification_if_another_user_change_view_ownership(
    mocked_broadcast_to_users, api_client, premium_data_fixture
):
    user_1 = premium_data_fixture.create_user(
        has_active_premium_license=True,
    )
    user_2 = premium_data_fixture.create_user(
        has_active_premium_license=True,
    )

    workspace = premium_data_fixture.create_workspace(members=[user_1, user_2])
    database = premium_data_fixture.create_database_application(
        user=user_1, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(
        name="Example", database=database
    )
    text_field = premium_data_fixture.create_text_field(name="text", table=table)
    number_field = premium_data_fixture.create_number_field(name="number", table=table)

    form = premium_data_fixture.create_form_view(table=table, public=True)
    premium_data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )
    premium_data_fixture.create_form_view_field_option(
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

    # user_2 change the ownership of the view to personal
    ViewHandler().update_view(
        user=user_2, view=form, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    mocked_broadcast_to_users.reset_mock()

    # user_1 will no longer receive notifications
    submit_form()

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert args[0][0] == [user_2.id]
