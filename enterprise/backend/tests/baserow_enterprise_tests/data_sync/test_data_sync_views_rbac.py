from django.urls import reverse

import pytest
import responses
from rest_framework.status import HTTP_401_UNAUTHORIZED

from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.fixture(autouse=True)
def _enable_rbac(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db(transaction=True)
@responses.activate
def test_viewer_role_denied_data_sync_properties_no_external_call(
    data_fixture, api_client
):
    """A workspace member with VIEWER role cannot access the data sync
    properties endpoint. No external network call should be made."""

    responses.add(
        responses.GET,
        "https://baserow.io/ical.ics",
        body="should not be called",
        status=200,
    )

    admin_user = data_fixture.create_user()
    viewer_user, viewer_token = data_fixture.create_user_and_token()
    database = data_fixture.create_database_application(user=admin_user)

    data_fixture.create_user_workspace(
        user=viewer_user,
        workspace=database.workspace,
        permissions="MEMBER",
    )
    viewer_role = RoleAssignmentHandler().get_role_by_uid("VIEWER")
    RoleAssignmentHandler().assign_role(
        viewer_user, database.workspace, role=viewer_role
    )

    url = reverse(
        "api:database:data_sync:properties",
        kwargs={"database_id": database.id},
    )
    response = api_client.post(
        url,
        {
            "type": "ical_calendar",
            "ical_url": "https://baserow.io/ical.ics",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {viewer_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert len(responses.calls) == 0
