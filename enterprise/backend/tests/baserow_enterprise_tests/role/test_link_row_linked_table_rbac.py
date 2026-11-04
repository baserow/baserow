from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.rows.actions import (
    UpdateRowActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.contrib.database.views.models import ViewDefaultValue
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowCreateRowsServiceType,
    LocalBaserowUpdateRowsServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import PermissionException
from baserow.core.jobs.tasks import run_async_job
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType

SECRET = "SECRET-XYZ99"
SESSION_ID = "session-id"


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


@pytest.mark.parametrize("name", ["Other", "Nope"])
@pytest.mark.django_db
def test_upsert_service_refuses_existing_and_missing_names_the_same_way(
    data_fixture, restricted_setup, name
):
    link = restricted_setup["link"]
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=restricted_setup["table"]
    )
    mapping = service.field_mappings.create(field=link, value="")

    with pytest.raises(PermissionException):
        LocalBaserowUpsertRowServiceType().dispatch_data(
            service,
            {mapping.id: [name]},
            FakeDispatchContext(actor=restricted_setup["user"]),
        )


@pytest.mark.parametrize("name", ["Other", "Nope"])
@pytest.mark.parametrize(
    "service_type,include_id",
    [
        (LocalBaserowCreateRowsServiceType, False),
        (LocalBaserowUpdateRowsServiceType, True),
    ],
)
@pytest.mark.django_db
def test_batch_services_refuse_existing_and_missing_names_the_same_way(
    data_fixture, restricted_setup, name, service_type, include_id
):
    create_service = (
        data_fixture.create_local_baserow_update_rows_service
        if include_id
        else data_fixture.create_local_baserow_create_rows_service
    )
    service = create_service(integration=None, table=restricted_setup["table"])
    row_values = {restricted_setup["link"].db_column: [name]}
    if include_id:
        row_values["id"] = restricted_setup["row"].id

    with pytest.raises(PermissionException):
        service_type().dispatch_data(
            service,
            {"rows": [row_values]},
            FakeDispatchContext(actor=restricted_setup["user"]),
        )


@pytest.mark.django_db
def test_clearing_a_link_can_be_undone_and_redone_without_the_linked_table(
    restricted_setup,
):
    user = restricted_setup["user"]
    table = restricted_setup["table"]
    row = restricted_setup["row"]
    field = f"field_{restricted_setup['link'].id}"
    scopes = [TableActionScopeType.value(table_id=table.id)]
    user.untrusted_client_session_id = SESSION_ID

    def linked_ids():
        linked_rows = getattr(table.get_model().objects.get(id=row.id), field)
        return [linked_row.id for linked_row in linked_rows.all()]

    hidden_row_id = restricted_setup["hidden_row"].id

    action_type_registry.get_by_type(UpdateRowsActionType).do(
        user, table, [{"id": row.id, field: []}]
    )
    assert linked_ids() == []

    undone = ActionHandler.undo(user, scopes, SESSION_ID)
    assert undone[0].error is None
    assert linked_ids() == [hidden_row_id]

    redone = ActionHandler.redo(user, scopes, SESSION_ID)
    assert redone[0].error is None
    assert linked_ids() == []


@pytest.mark.django_db
def test_clearing_a_link_on_a_single_row_can_be_undone_without_the_linked_table(
    restricted_setup,
):
    user = restricted_setup["user"]
    table = restricted_setup["table"]
    row = restricted_setup["row"]
    field = f"field_{restricted_setup['link'].id}"
    scopes = [TableActionScopeType.value(table_id=table.id)]
    user.untrusted_client_session_id = SESSION_ID

    action_type_registry.get_by_type(UpdateRowActionType).do(
        user, table, row.id, {field: []}
    )

    undone = ActionHandler.undo(user, scopes, SESSION_ID)

    assert undone[0].error is None
    linked_rows = getattr(table.get_model().objects.get(id=row.id), field)
    assert [linked_row.id for linked_row in linked_rows.all()] == [
        restricted_setup["hidden_row"].id
    ]


def upsert_import_configuration(setup):
    name_field = setup["table"].field_set.get(name="Name")
    return name_field, {
        "import_fields": [name_field.id, setup["link"].id],
        "upsert_fields": [name_field.id],
        "upsert_values": [["A"]],
        "skipped_fields": [setup["link"].id],
    }


@pytest.mark.django_db
def test_upsert_import_of_a_matched_row_ignores_a_skipped_link_column(
    restricted_setup,
):
    row = restricted_setup["row"]
    table = restricted_setup["table"]
    link = restricted_setup["link"]
    name_field, configuration = upsert_import_configuration(restricted_setup)
    model = table.get_model()
    model.objects.filter(id=row.id).update(**{name_field.db_column: "A"})

    RowHandler().import_rows(
        restricted_setup["user"],
        table,
        [["A", "Other"]],
        configuration=configuration,
    )

    linked_rows = getattr(model.objects.get(id=row.id), link.db_column).all()
    assert [linked_row.id for linked_row in linked_rows] == [
        restricted_setup["hidden_row"].id
    ]
    assert model.objects.count() == 1


@pytest.mark.django_db
def test_upsert_import_of_an_unmatched_row_checks_a_skipped_link_column(
    restricted_setup,
):
    _, configuration = upsert_import_configuration(restricted_setup)

    with pytest.raises(PermissionException):
        RowHandler().import_rows(
            restricted_setup["user"],
            restricted_setup["table"],
            [["A", "Other"]],
            configuration=configuration,
        )


@pytest.mark.django_db
def test_file_import_says_why_a_link_column_was_refused(
    data_fixture, patch_filefield_storage, restricted_setup
):
    with patch_filefield_storage():
        job = data_fixture.create_file_import_job(
            user=restricted_setup["user"],
            table=restricted_setup["table"],
            data={
                "data": [["Other"]],
                "configuration": {"import_fields": [restricted_setup["link"].id]},
            },
        )
        run_async_job(job.id)

    job.refresh_from_db()
    assert job.state == "failed"
    assert "linked table" in job.human_readable_error


@pytest.fixture
def restricted_view_setup(data_fixture, enterprise_data_fixture):
    admin = data_fixture.create_user()
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[user])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(table=table, primary=True, name="Name")
    link = data_fixture.create_link_row_field(
        table=table, link_row_table=table, name="Self"
    )
    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    data_fixture.create_view_filter(
        view=view, field=primary, type="not_equal", value="Hidden"
    )
    handler = RowHandler()
    visible_row = handler.create_row(admin, table, {primary.db_column: "Visible"})
    hidden_row = handler.create_row(admin, table, {primary.db_column: "Hidden"})

    role_handler = RoleAssignmentHandler()
    role_handler.assign_role(
        user, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=workspace
    )
    role_handler.assign_role(
        user, workspace, role=Role.objects.get(uid="EDITOR"), scope=view
    )
    return {
        "user": user,
        "table": table,
        "view": view,
        "link": link,
        "visible_row": visible_row,
        "hidden_row": hidden_row,
    }


def post_self_link(api_client, data_fixture, setup, value):
    jwt = data_fixture.generate_token(setup["user"])
    url = reverse("api:database:rows:list", kwargs={"table_id": setup["table"].id})
    return api_client.post(
        f"{url}?view={setup['view'].id}",
        {setup["link"].db_column: value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt}",
    )


@pytest.mark.django_db
def test_restricted_view_editor_can_self_link_a_row_of_the_view(
    api_client, data_fixture, restricted_view_setup
):
    response = post_self_link(
        api_client,
        data_fixture,
        restricted_view_setup,
        [restricted_view_setup["visible_row"].id],
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.parametrize("value", ["id", "Hidden", "Nope"])
@pytest.mark.django_db
def test_restricted_view_editor_can_not_self_link_a_row_outside_the_view(
    api_client, data_fixture, restricted_view_setup, value
):
    target = restricted_view_setup["hidden_row"].id if value == "id" else value

    response = post_self_link(api_client, data_fixture, restricted_view_setup, [target])

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"
    assert "Hidden" not in response.content.decode()


@pytest.mark.django_db
def test_view_default_link_is_refused_when_the_role_hides_the_linked_table(
    enterprise_data_fixture, restricted_setup
):
    table = restricted_setup["table"]
    view = enterprise_data_fixture.create_grid_view(table=table)
    ViewDefaultValue.objects.create(
        view=view,
        field=restricted_setup["link"],
        value=[restricted_setup["hidden_row"].id],
        field_type="link_row",
    )
    user = restricted_setup["user"]

    with pytest.raises(PermissionException):
        RowHandler().create_row(user, table, {}, view=view)
    with pytest.raises(PermissionException):
        RowHandler().create_rows(user, table, [{}], view=view)


def count_join_queries(api_client, url, auth):
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get(url, HTTP_AUTHORIZATION=auth)
    assert response.status_code == HTTP_200_OK
    return len(queries)


@pytest.mark.parametrize("use_token", [False, True])
@pytest.mark.django_db
def test_join_check_queries_do_not_grow_with_links_to_the_same_table(
    api_client, data_fixture, restricted_setup, use_token
):
    """
    Measures the queries the check adds, as the difference with the check switched off,
    for few and for many link fields to one table the user is a viewer of.
    """

    user = restricted_setup["user"]
    table = restricted_setup["table"]
    target = restricted_setup["secret"].table
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user, workspace, role=Role.objects.get(uid="VIEWER"), scope=target
    )
    links = [restricted_setup["link"]] + [
        data_fixture.create_link_row_field(
            table=table, link_row_table=target, name=f"Link {index}"
        )
        for index in range(29)
    ]
    if use_token:
        token = TokenHandler().create_token(user, workspace, "Scoped")
        auth = f"Token {token.key}"
    else:
        auth = f"JWT {data_fixture.generate_token(user)}"

    def join_url(count):
        secret_id = restricted_setup["secret"].id
        params = "&".join(
            f"field_{link.id}__join=field_{secret_id}" for link in links[:count]
        )
        url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
        return f"{url}?{params}"

    def added_queries(count):
        url = join_url(count)
        count_join_queries(api_client, url, auth)
        with_check = count_join_queries(api_client, url, auth)
        with patch("baserow.contrib.database.api.utils.check_can_list_rows_of_tables"):
            without_check = count_join_queries(api_client, url, auth)
        return with_check - without_check

    assert added_queries(30) <= added_queries(2)
