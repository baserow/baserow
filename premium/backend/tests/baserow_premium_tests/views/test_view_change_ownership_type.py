from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.views.models import OWNERSHIP_TYPE_COLLABORATIVE
from baserow.core.handler import CoreHandler
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL
from baserow_premium.views.view_ownership_types import PersonalViewOwnershipType


@override_settings(PERMISSION_MANAGERS=["basic"])
@pytest.mark.django_db
def test_patch_view_validate_ownerhip_type_valid_types(
    api_client,
    data_fixture,
    premium_data_fixture,
    alternative_per_workspace_license_service,
):
    """A test to make sure that if a valid `ownership_type` string is passed
    when updating the view, the `ownership_type` is updated and this results
    in status 200 error w/o an error message.

    Note, that the case of non-existent `ownership_type` string is tested in core
    (see: `test_patch_view_validate_ownerhip_type_invalid_type` method)
    """

    workspace = premium_data_fixture.create_workspace(name="Workspace 1")
    user, token = premium_data_fixture.create_user_and_token(workspace=workspace)
    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, workspace.id
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(
        user=user,
        database=database,
    )
    view = premium_data_fixture.create_grid_view(
        user=user,
        table=table,
        ownership_type=OWNERSHIP_TYPE_PERSONAL,
    )

    # 1. test case of personal -> collaborative ownership type:
    data = {"ownership_type": OWNERSHIP_TYPE_COLLABORATIVE}
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_data = response.json()

    assert response.status_code == HTTP_200_OK
    view.refresh_from_db()
    assert view.ownership_type == OWNERSHIP_TYPE_COLLABORATIVE
    assert response_data["ownership_type"] == OWNERSHIP_TYPE_COLLABORATIVE

    # 2. test case of collaborative -> personal ownership type:
    data = {"ownership_type": OWNERSHIP_TYPE_PERSONAL}
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": view.id}),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_data = response.json()

    assert response.status_code == HTTP_200_OK
    view.refresh_from_db()
    assert view.ownership_type == OWNERSHIP_TYPE_PERSONAL
    assert response_data["ownership_type"] == OWNERSHIP_TYPE_PERSONAL


@pytest.mark.django_db
def test_personal_view_import_accepts_only_people_without_a_query_per_owner(
    data_fixture, django_assert_num_queries
):
    workspace = data_fixture.create_workspace()
    people = [data_fixture.create_user(workspace=workspace) for _ in range(3)]
    identity = data_fixture.create_identity(workspace=workspace)
    id_mapping = {"owned_by": CoreHandler.get_user_email_mapping(workspace.id, [])}
    ownership_type = PersonalViewOwnershipType()

    with django_assert_num_queries(0):
        imported = [
            ownership_type.can_import_view({"owned_by": user.email}, id_mapping)
            for user in [*people, identity]
        ]

    assert imported == [True, True, True, False]
