from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db()
def test_queries_to_list_apps_should_not_increase_with_the_number_of_applications(
    api_client, data_fixture, enterprise_data_fixture
):
    admin = data_fixture.create_user()
    user_2, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=admin, members=[user_2])
    viewer_role = Role.objects.get(uid="VIEWER")

    def _create_db_with_two_table():
        database = data_fixture.create_database_application(
            user=admin, workspace=workspace
        )
        table1 = data_fixture.create_database_table(user=admin, database=database)
        table2 = data_fixture.create_database_table(user=admin, database=database)
        RoleAssignmentHandler().assign_role(
            user_2, workspace, role=viewer_role, scope=table2
        )

    def _create_builder_with_two_pages():
        builder = data_fixture.create_builder_application(
            user=admin, workspace=workspace
        )
        page1 = data_fixture.create_builder_page(user=admin, builder=builder)
        page2 = data_fixture.create_builder_page(user=admin, builder=builder)

    _create_db_with_two_table()

    _create_builder_with_two_pages()

    url = reverse("api:applications:list")

    def _get_apps():
        rsp = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")
        assert rsp.status_code == HTTP_200_OK

    # The first call have some inserts for various themes config blocks
    _get_apps()

    with CaptureQueriesContext(connection) as captured:
        _get_apps()
        captured_queries = list(captured.captured_queries)

    _create_db_with_two_table()
    _create_db_with_two_table()
    _create_db_with_two_table()

    _create_builder_with_two_pages()
    _create_builder_with_two_pages()

    # The first call have some inserts for various themes config blocks
    _get_apps()

    with CaptureQueriesContext(connection) as captured2:
        _get_apps()

    assert len(captured_queries) == len(captured2.captured_queries)


@pytest.mark.django_db
def test_list_workspace_applications(data_fixture, enterprise_data_fixture, api_client):
    admin = data_fixture.create_user()
    user_2, token = data_fixture.create_user_and_token()

    builder_role = Role.objects.get(uid="BUILDER")
    no_role_role = Role.objects.get(uid="NO_ACCESS")

    wp1 = data_fixture.create_workspace(
        name="Workspace 1", user=admin, members=[user_2]
    )

    db1 = data_fixture.create_database_application(workspace=wp1, name="Database 1")
    table1 = data_fixture.create_database_table(
        user=admin, database=db1, name="Table 1"
    )

    RoleAssignmentHandler().assign_role(user_2, wp1, role=no_role_role, scope=wp1)
    RoleAssignmentHandler().assign_role(user_2, wp1, role=builder_role, scope=table1)

    wp2 = data_fixture.create_workspace(
        name="Workspace 2", user=admin, members=[user_2]
    )
    db2 = data_fixture.create_database_application(workspace=wp2, name="Database 2")
    table2 = data_fixture.create_database_table(
        user=admin, database=db2, name="Table 2"
    )

    RoleAssignmentHandler().assign_role(user_2, wp2, role=no_role_role, scope=wp2)
    RoleAssignmentHandler().assign_role(user_2, wp2, role=builder_role, scope=table2)

    url = reverse("api:applications:list")
    rsp = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert rsp.status_code == HTTP_200_OK
    assert len(rsp.data) == 2
    assert rsp.data == [
        {
            "id": db1.id,
            "name": "Database 1",
            "order": 0,
            "type": "database",
            "workspace": {
                "id": wp1.id,
                "name": "Workspace 1",
                "generative_ai_models_enabled": {},
            },
            "created_on": AnyStr(),
            "tables": [
                {
                    "id": table1.id,
                    "name": "Table 1",
                    "order": 0,
                    "database_id": db1.id,
                    "data_sync": None,
                }
            ],
        },
        {
            "id": db2.id,
            "name": "Database 2",
            "order": 0,
            "type": "database",
            "workspace": {
                "id": wp2.id,
                "name": "Workspace 2",
                "generative_ai_models_enabled": {},
            },
            "created_on": AnyStr(),
            "tables": [
                {
                    "id": table2.id,
                    "name": "Table 2",
                    "order": 0,
                    "database_id": db2.id,
                    "data_sync": None,
                }
            ],
        },
    ]
