from datetime import datetime, timezone

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.models import Workspace


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_admin_workspaces(api_client, data_fixture, django_assert_num_queries):
    """
    This endpoint doesn't need to be tested extensively because it uses the same base
    class as the list users endpoint which already has extensive tests. We only need to
    test if the functionality works in a basic form.
    """

    created = datetime(2020, 4, 10, 0, 0, 0).replace(tzinfo=timezone.utc)
    staff_user, staff_token = data_fixture.create_user_and_token(is_staff=True)
    normal_user, normal_token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(name="A")
    workspace_1.created_on = created
    workspace_1.save()
    workspace_2 = data_fixture.create_workspace(name="B", created_on=created)
    workspace_2.created_on = created
    workspace_2.save()
    template_workspace = data_fixture.create_workspace(
        name="Template", created_on=created
    )
    data_fixture.create_template(workspace=template_workspace)
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=normal_user, permissions="MEMBER"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_2, user=normal_user, permissions="ADMIN"
    )
    data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_application(workspace=workspace_1)

    response = api_client.get(
        reverse("api:admin:workspaces:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    with django_assert_num_queries(5):
        response = api_client.get(
            reverse("api:admin:workspaces:list"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {staff_token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": workspace_1.id,
                "name": workspace_1.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "MEMBER",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 2,
                "created_on": "2020-04-10T00:00:00Z",
            },
            {
                "id": workspace_2.id,
                "name": workspace_2.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "ADMIN",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 0,
                "created_on": "2020-04-10T00:00:00Z",
            },
        ],
    }

    response = api_client.get(
        f'{reverse("api:admin:workspaces:list")}?search={workspace_1.name}',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {staff_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": workspace_1.id,
                "name": workspace_1.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "MEMBER",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 2,
                "created_on": "2020-04-10T00:00:00Z",
            },
        ],
    }

    response = api_client.get(
        f'{reverse("api:admin:workspaces:list")}?sorts=-name',
        format="json",
        HTTP_AUTHORIZATION=f"JWT {staff_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": workspace_2.id,
                "name": workspace_2.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "ADMIN",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 0,
                "created_on": "2020-04-10T00:00:00Z",
            },
            {
                "id": workspace_1.id,
                "name": workspace_1.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "MEMBER",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 2,
                "created_on": "2020-04-10T00:00:00Z",
            },
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_workspace(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token()
    staff_user, staff_token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace()

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": 99999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {staff_token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {normal_token}")
    assert response.status_code == HTTP_403_FORBIDDEN

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {staff_token}")
    assert response.status_code == 204
    assert Workspace.objects.all().count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_delete_template_workspace(api_client, data_fixture):
    staff_user, staff_token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace)

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {staff_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP"
    assert Workspace.objects.all().count() == 1
