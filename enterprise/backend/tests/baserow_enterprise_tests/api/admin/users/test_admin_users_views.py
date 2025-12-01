from datetime import datetime, timezone

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK

from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    WORKSPACE_USER_PERMISSION_MEMBER,
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_users_endpoint_contains_highest_role(
    api_client, data_fixture, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    staff_user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        is_staff=True,
        date_joined=datetime(2021, 4, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    workspace_user_is_admin_of = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_user_is_admin_of,
        user=staff_user,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )
    workspace_user_is_not_admin_of = data_fixture.create_workspace()
    data_fixture.create_user_workspace(
        workspace=workspace_user_is_not_admin_of,
        user=staff_user,
        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
    )
    response = api_client.get(
        reverse("api:admin:users:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "date_joined": "2021-04-01T01:00:00Z",
                "name": staff_user.first_name,
                "username": staff_user.email,
                "highest_role_uid": "ADMIN",
                "workspaces": unordered(
                    [
                        {
                            "id": workspace_user_is_admin_of.id,
                            "name": workspace_user_is_admin_of.name,
                            "permissions": WORKSPACE_USER_PERMISSION_ADMIN,
                        },
                        {
                            "id": workspace_user_is_not_admin_of.id,
                            "name": workspace_user_is_not_admin_of.name,
                            "permissions": WORKSPACE_USER_PERMISSION_MEMBER,
                        },
                    ]
                ),
                "id": staff_user.id,
                "is_staff": True,
                "is_active": True,
                "last_login": None,
            }
        ],
    }
