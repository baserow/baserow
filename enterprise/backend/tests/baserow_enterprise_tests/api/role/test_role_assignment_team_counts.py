from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest

from baserow_enterprise.api.role.serializers import RoleAssignmentSerializer
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role, RoleAssignment


@pytest.fixture(autouse=True)
def enable_roles(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["list", "create", "batch"])
def test_role_assignment_responses_include_team_member_counts(
    api_client, data_fixture, enterprise_data_fixture, endpoint
):
    """Team counts must be correct on initial load and immediately after a role edit."""

    admin, token = data_fixture.create_user_and_token()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    database = data_fixture.create_database_application(workspace=workspace)
    populated = enterprise_data_fixture.create_team(
        workspace=workspace, members=[admin, member]
    )
    empty = enterprise_data_fixture.create_team(workspace=workspace)
    payloads = [
        {
            "subject_type": "baserow_enterprise.Team",
            "subject_id": team.id,
            "scope_type": "application",
            "scope_id": database.id,
            "role": "EDITOR",
        }
        for team in [populated, empty]
    ]
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:enterprise:role:list", kwargs={"workspace_id": workspace.id})
    if endpoint == "list":
        for team in [populated, empty]:
            RoleAssignmentHandler().assign_role(
                team,
                workspace,
                Role.objects.get(uid="EDITOR"),
                database.application_ptr,
            )
        response = api_client.get(
            url, {"scope_type": "application", "scope_id": database.id}, **headers
        )
        assert response.status_code == 200
        assignments = response.json()
    elif endpoint == "batch":
        response = api_client.post(
            reverse("api:enterprise:role:batch", kwargs={"workspace_id": workspace.id}),
            {"items": payloads},
            format="json",
            **headers,
        )
        assert response.status_code == 200
        assignments = response.json()
    else:
        assignments = []
        for payload in payloads:
            response = api_client.post(url, payload, format="json", **headers)
            assert response.status_code == 200
            assignments.append(response.json())

    assert {
        item["subject"]["id"]: item["subject"]["subject_count"] for item in assignments
    } == {populated.id: 2, empty.id: 0}


@pytest.mark.django_db
@pytest.mark.parametrize("loading_path", ["list", "mutation"])
def test_team_role_counts_are_prefetched_without_queries_per_team(
    data_fixture, enterprise_data_fixture, loading_path
):
    """Fetching and serializing a larger access list must batch team count lookups."""

    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    database = data_fixture.create_database_application(workspace=workspace)
    handler = RoleAssignmentHandler()
    role = Role.objects.get(uid="EDITOR")

    def add_team():
        team = enterprise_data_fixture.create_team(workspace=workspace, members=[admin])
        handler.assign_role(team, workspace, role, database.application_ptr)

    def read_counts():
        """Load subjects once and require serialization to perform no queries."""

        if loading_path == "list":
            assignments = handler.get_role_assignments(
                workspace, database.application_ptr
            )
        else:
            assignments = list(
                RoleAssignment.objects.filter(workspace=workspace).select_related(
                    "role", "subject_type", "scope_type"
                )
            )
        handler.prefetch_role_assignment_subjects([*assignments, None])
        with CaptureQueriesContext(connection) as serialization_queries:
            data = RoleAssignmentSerializer(assignments, many=True).data
        assert len(serialization_queries) == 0
        return [item["subject"]["subject_count"] for item in data]

    add_team()
    assert read_counts() == [1]  # Warm the content-type and role caches.
    with CaptureQueriesContext(connection) as small:
        assert read_counts() == [1]
    for _ in range(7):
        add_team()
    with CaptureQueriesContext(connection) as large:
        assert read_counts() == [1] * 8
    assert len(large) == len(small)
