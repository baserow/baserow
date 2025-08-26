from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.core.subjects import UserSubjectType
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_create_restricted_grid_view_without_license(
    api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "restricted",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_restricted_grid_view_with_license(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "ownership_type": "restricted",
            "filter_type": "OR",
            "filters_disabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["ownership_type"] == "restricted"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_create_view_if_user_has_only_permissions_to_view(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[])
    enterprise_data_fixture.create_user_workspace(
        workspace=workspace, user=user2, permissions="NO_ACCESS", order=0
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(user=user, database=database)
    view = enterprise_data_fixture.create_grid_view(table=table)

    editor_role = Role.objects.get(uid="EDITOR")

    response = api_client.post(
        reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id}),
        {
            "items": [
                {
                    "scope_id": view.id,
                    "scope_type": "database_view",
                    "subject_id": user2.id,
                    "subject_type": UserSubjectType.type,
                    "role": editor_role.uid,
                },
            ]
        },
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
            "ownership_type": "collaborative",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
            "ownership_type": "personal",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 1",
            "type": "grid",
            "filter_type": "OR",
            "filters_disabled": True,
            "ownership_type": "restricted",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
