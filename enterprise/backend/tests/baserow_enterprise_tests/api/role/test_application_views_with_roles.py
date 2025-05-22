from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

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

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})

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
