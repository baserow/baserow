from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_401_UNAUTHORIZED

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import PermissionException
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role

SECRET = "SECRET-XYZ99"


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.fixture
def restricted_setup(data_fixture):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True, name="Name")
    hidden_table = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(
        table=hidden_table, primary=True, name="Name"
    )
    secret = data_fixture.create_text_field(table=hidden_table, name="Secret")
    link = data_fixture.create_link_row_field(
        table=table, link_row_table=hidden_table, name="Link"
    )
    hidden_row = RowHandler().create_row(
        admin,
        hidden_table,
        {f"field_{primary.id}": "Other", f"field_{secret.id}": SECRET},
    )
    row = RowHandler().create_row(admin, table, {f"field_{link.id}": [hidden_row.id]})

    RoleAssignmentHandler().assign_role(
        user, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=hidden_table
    )
    return {
        "user": user,
        "table": table,
        "link": link,
        "secret": secret,
        "row": row,
        "hidden_row": hidden_row,
    }


@pytest.mark.django_db
def test_join_is_refused_when_the_role_hides_the_linked_table(
    api_client, data_fixture, restricted_setup
):
    jwt = data_fixture.generate_token(restricted_setup["user"])
    url = reverse(
        "api:database:rows:list", kwargs={"table_id": restricted_setup["table"].id}
    )
    link_id = restricted_setup["link"].id
    secret_id = restricted_setup["secret"].id

    response = api_client.get(
        f"{url}?field_{link_id}__join=field_{secret_id}",
        HTTP_AUTHORIZATION=f"JWT {jwt}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"
    assert SECRET not in response.content.decode()


@pytest.mark.django_db
def test_linking_is_refused_when_the_role_hides_the_linked_table(
    api_client, data_fixture, restricted_setup
):
    jwt = data_fixture.generate_token(restricted_setup["user"])
    field = f"field_{restricted_setup['link'].id}"

    response = api_client.post(
        reverse(
            "api:database:rows:list", kwargs={"table_id": restricted_setup["table"].id}
        ),
        {field: [restricted_setup["hidden_row"].id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"
    assert "Other" not in response.content.decode()


@pytest.mark.django_db
def test_handler_refuses_links_when_the_role_hides_the_linked_table(restricted_setup):
    user = restricted_setup["user"]
    table = restricted_setup["table"]
    row = restricted_setup["row"]
    values = {f"field_{restricted_setup['link'].id}": [row.id]}
    handler = RowHandler()

    with pytest.raises(PermissionException):
        handler.create_row(user, table, dict(values))
    with pytest.raises(PermissionException):
        handler.create_rows(user, table, [dict(values)])
    with pytest.raises(PermissionException):
        handler.update_row(user, table, row, dict(values))
    with pytest.raises(PermissionException):
        handler.update_rows(user, table, [{"id": row.id, **values}])


@pytest.mark.django_db
def test_import_refuses_links_when_the_role_hides_the_linked_table(restricted_setup):
    user = restricted_setup["user"]
    table = restricted_setup["table"]
    link = restricted_setup["link"]

    with pytest.raises(PermissionException):
        RowHandler().import_rows(
            user,
            table,
            [["Other"]],
            configuration={"import_fields": [link.id]},
        )


@pytest.mark.django_db
def test_clearing_links_is_allowed_when_the_role_hides_the_linked_table(
    restricted_setup,
):
    user = restricted_setup["user"]
    table = restricted_setup["table"]
    row = restricted_setup["row"]
    field = f"field_{restricted_setup['link'].id}"

    RowHandler().update_rows(user, table, [{"id": row.id, field: []}])

    assert list(getattr(table.get_model().objects.get(id=row.id), field).all()) == []
