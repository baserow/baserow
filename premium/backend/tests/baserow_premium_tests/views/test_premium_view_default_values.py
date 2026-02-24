from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from baserow.core.models import WorkspaceUser
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL


@pytest.mark.django_db
def test_get_default_values_user_personal_view_denied(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    user, _ = premium_data_fixture.create_user_and_token()
    user_2, token_2 = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_2, workspace=workspace, permissions="MEMBER", order=1
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user_2, workspace.id
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database, user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="Text")
    grid = premium_data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_patch_default_values_user_personal_view_denied(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    user, _ = premium_data_fixture.create_user_and_token()
    user_2, token_2 = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_2, workspace=workspace, permissions="MEMBER", order=1
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user_2, workspace.id
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database, user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="Text")
    grid = premium_data_fixture.create_grid_view(
        table=table, user=user, owned_by=user, ownership_type=OWNERSHIP_TYPE_PERSONAL
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED, response.json()
    response_json = response.json()
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_get_default_values_user_personal_view_allowed(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    user, _ = premium_data_fixture.create_user_and_token()
    user_2, token_2 = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_2, workspace=workspace, permissions="MEMBER", order=1
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user_2, workspace.id
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database, user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="Text")
    grid = premium_data_fixture.create_grid_view(
        table=table,
        user=user_2,
        owned_by=user_2,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()


@pytest.mark.django_db
def test_patch_default_values_user_personal_view_allowed(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    user, _ = premium_data_fixture.create_user_and_token()
    user_2, token_2 = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    WorkspaceUser.objects.create(
        user=user_2, workspace=workspace, permissions="MEMBER", order=1
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user_2, workspace.id
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database, user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="Text")
    grid = premium_data_fixture.create_grid_view(
        table=table,
        user=user_2,
        owned_by=user_2,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )

    url = reverse("api:database:views:default_values", kwargs={"view_id": grid.id})
    response = api_client.patch(
        url,
        {text_field.id: {"value": None}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
