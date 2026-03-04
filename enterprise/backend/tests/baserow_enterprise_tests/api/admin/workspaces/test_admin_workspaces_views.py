from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_list_workspaces_as_options(api_client, enterprise_data_fixture):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    workspace_1 = enterprise_data_fixture.create_workspace(
        name="workspace 1", user=admin_user
    )
    workspace_2 = enterprise_data_fixture.create_workspace(
        name="workspace 2", user=admin_user
    )

    # no search query should return all workspaces
    response = api_client.get(
        reverse("api:enterprise:admin:workspaces:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": workspace_1.id, "value": workspace_1.name},
            {"id": workspace_2.id, "value": workspace_2.name},
        ],
    }

    # searching by name should return only the correct workspace
    response = api_client.get(
        reverse("api:enterprise:admin:workspaces:list") + "?search=1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": workspace_1.id, "value": workspace_1.name}],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_list_workspaces_as_options_filter_by_ids(
    api_client, enterprise_data_fixture
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    workspace_1 = enterprise_data_fixture.create_workspace(
        name="workspace 1", user=admin_user
    )
    workspace_2 = enterprise_data_fixture.create_workspace(
        name="workspace 2", user=admin_user
    )
    enterprise_data_fixture.create_workspace(name="workspace 3", user=admin_user)

    # filtering by a single id should return only that workspace
    response = api_client.get(
        reverse("api:enterprise:admin:workspaces:list") + f"?ids={workspace_1.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": workspace_1.id, "value": workspace_1.name}],
    }

    # filtering by multiple ids should return all matching workspaces
    response = api_client.get(
        reverse("api:enterprise:admin:workspaces:list")
        + f"?ids={workspace_1.id},{workspace_2.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": workspace_1.id, "value": workspace_1.name},
            {"id": workspace_2.id, "value": workspace_2.name},
        ],
    }
