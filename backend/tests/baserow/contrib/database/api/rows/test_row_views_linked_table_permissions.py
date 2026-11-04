from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.tokens.handler import TokenHandler

SECRET = "SECRET-XYZ99"


@pytest.fixture
def linked_tables(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, primary=True, name="Name")
    other_table = data_fixture.create_database_table(database=database)
    primary = data_fixture.create_text_field(
        table=other_table, primary=True, name="Name"
    )
    secret = data_fixture.create_text_field(table=other_table, name="Secret")
    link = data_fixture.create_link_row_field(
        table=table, link_row_table=other_table, name="Link"
    )
    other_row = RowHandler().create_row(
        user,
        other_table,
        {f"field_{primary.id}": "Other", f"field_{secret.id}": SECRET},
    )
    row = RowHandler().create_row(user, table, {f"field_{link.id}": [other_row.id]})
    return {
        "user": user,
        "table": table,
        "other_table": other_table,
        "link": link,
        "secret": secret,
        "primary": primary,
        "row": row,
        "other_row": other_row,
    }


def scoped_token(setup, can_read_other_table):
    table = setup["table"]
    read_tables = [table]
    if can_read_other_table:
        read_tables.append(setup["other_table"])
    token = TokenHandler().create_token(
        setup["user"], table.database.workspace, "Scoped"
    )
    TokenHandler().update_token_permissions(
        setup["user"],
        token,
        create=[table],
        read=read_tables,
        update=[table],
        delete=False,
    )
    return f"Token {token.key}"


def join_url(setup):
    url = reverse("api:database:rows:list", kwargs={"table_id": setup["table"].id})
    return f"{url}?field_{setup['link'].id}__join=field_{setup['secret'].id}"


def write_link(api_client, setup, endpoint, value, auth):
    table_id = setup["table"].id
    field = f"field_{setup['link'].id}"
    row_id = setup["row"].id
    if endpoint == "create":
        return api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table_id}),
            {field: value},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
    if endpoint == "update":
        return api_client.patch(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table_id, "row_id": row_id},
            ),
            {field: value},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
    if endpoint == "batch_create":
        return api_client.post(
            reverse("api:database:rows:batch", kwargs={"table_id": table_id}),
            {"items": [{field: value}]},
            format="json",
            HTTP_AUTHORIZATION=auth,
        )
    return api_client.patch(
        reverse("api:database:rows:batch", kwargs={"table_id": table_id}),
        {"items": [{"id": row_id, field: value}]},
        format="json",
        HTTP_AUTHORIZATION=auth,
    )


WRITE_ENDPOINTS = ["create", "update", "batch_create", "batch_update"]


@pytest.mark.django_db
def test_join_is_refused_without_read_access_to_the_linked_table(
    api_client, linked_tables
):
    auth = scoped_token(linked_tables, can_read_other_table=False)

    response = api_client.get(join_url(linked_tables), HTTP_AUTHORIZATION=auth)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"
    assert SECRET not in response.content.decode()


@pytest.mark.django_db
def test_join_returns_values_with_read_access_to_the_linked_table(
    api_client, linked_tables
):
    auth = scoped_token(linked_tables, can_read_other_table=True)

    response = api_client.get(join_url(linked_tables), HTTP_AUTHORIZATION=auth)

    assert response.status_code == HTTP_200_OK
    assert SECRET in response.content.decode()


@pytest.mark.django_db
def test_listing_without_join_still_works_without_access_to_the_linked_table(
    api_client, linked_tables
):
    auth = scoped_token(linked_tables, can_read_other_table=False)

    response = api_client.get(
        reverse(
            "api:database:rows:list", kwargs={"table_id": linked_tables["table"].id}
        ),
        HTTP_AUTHORIZATION=auth,
    )

    assert response.status_code == HTTP_200_OK
    assert SECRET not in response.content.decode()


@pytest.mark.django_db
def test_join_on_a_self_referencing_link_needs_no_extra_table_access(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    primary = data_fixture.create_text_field(table=table, primary=True, name="Name")
    link = data_fixture.create_link_row_field(table=table, link_row_table=table)
    token = TokenHandler().create_token(user, table.database.workspace, "Scoped")
    TokenHandler().update_token_permissions(
        user, token, create=False, read=[table], update=False, delete=False
    )

    url = reverse("api:database:rows:list", kwargs={"table_id": table.id})
    response = api_client.get(
        f"{url}?field_{link.id}__join=field_{primary.id}",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.parametrize("endpoint", WRITE_ENDPOINTS)
@pytest.mark.parametrize("by_name", [False, True])
@pytest.mark.django_db
def test_linking_rows_is_refused_without_read_access_to_the_linked_table(
    api_client, linked_tables, endpoint, by_name
):
    auth = scoped_token(linked_tables, can_read_other_table=False)
    value = ["Other"] if by_name else [linked_tables["other_row"].id]

    response = write_link(api_client, linked_tables, endpoint, value, auth)

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_PERMISSION_TO_TABLE"
    assert "Other" not in response.content.decode()


@pytest.mark.parametrize("endpoint", WRITE_ENDPOINTS)
@pytest.mark.django_db
def test_linking_rows_works_with_read_access_to_the_linked_table(
    api_client, linked_tables, endpoint
):
    auth = scoped_token(linked_tables, can_read_other_table=True)
    value = [linked_tables["other_row"].id]

    response = write_link(api_client, linked_tables, endpoint, value, auth)

    assert response.status_code == HTTP_200_OK


@pytest.mark.parametrize("endpoint", WRITE_ENDPOINTS)
@pytest.mark.django_db
def test_clearing_links_needs_no_access_to_the_linked_table(
    api_client, linked_tables, endpoint
):
    auth = scoped_token(linked_tables, can_read_other_table=False)

    response = write_link(api_client, linked_tables, endpoint, [], auth)

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_updating_other_fields_needs_no_access_to_the_linked_table(
    api_client, linked_tables, data_fixture
):
    text_field = data_fixture.create_text_field(
        table=linked_tables["table"], name="Text"
    )
    auth = scoped_token(linked_tables, can_read_other_table=False)

    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={
                "table_id": linked_tables["table"].id,
                "row_id": linked_tables["row"].id,
            },
        ),
        {f"field_{text_field.id}": "changed"},
        format="json",
        HTTP_AUTHORIZATION=auth,
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_jwt_user_with_workspace_access_can_join_and_link(
    api_client, data_fixture, linked_tables
):
    jwt = data_fixture.generate_token(linked_tables["user"])

    join = api_client.get(join_url(linked_tables), HTTP_AUTHORIZATION=f"JWT {jwt}")
    write = write_link(
        api_client,
        linked_tables,
        "create",
        [linked_tables["other_row"].id],
        f"JWT {jwt}",
    )

    assert join.status_code == HTTP_200_OK
    assert SECRET in join.content.decode()
    assert write.status_code == HTTP_200_OK
