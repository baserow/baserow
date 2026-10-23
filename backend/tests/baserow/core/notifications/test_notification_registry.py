from django.test.utils import override_settings

import pytest

from baserow.core.models import Notification


@pytest.mark.django_db
def test_get_web_frontend_url(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    notification = data_fixture.create_workspace_notification_for_users(
        recipients=[user], workspace=workspace
    )

    assert notification.web_frontend_url is None


@pytest.mark.django_db
def test_get_web_frontend_url_with_notification_that_has_url(data_fixture):
    workspace = data_fixture.create_workspace()
    notification = Notification.objects.create(
        type="form_submitted",
        workspace_id=workspace.id,
        data={
            "row_id": 1,
            "values": [["Name", "1"]],
            "form_id": 1,
            "table_id": 2,
            "form_name": "Form",
            "table_name": "Table",
            "database_id": 3,
        },
    )

    assert notification.web_frontend_url == (
        f"http://localhost:3000/notification/{workspace.id}/{notification.id}"
    )


@pytest.mark.django_db
@override_settings(BASEROW_EMBEDDED_SHARE_URL="https://embed.example/baserow/")
def test_get_web_frontend_url_keeps_the_embedded_share_url_path(data_fixture):
    workspace = data_fixture.create_workspace()
    notification = Notification.objects.create(
        type="form_submitted", workspace_id=workspace.id, data={}
    )

    assert notification.web_frontend_url == (
        f"https://embed.example/baserow/notification/{workspace.id}/{notification.id}"
    )
