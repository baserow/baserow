from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.core.user_sources.user_source_user import UserSourceUser


@pytest.fixture
def data_source_fixture(data_fixture):
    """A fixture to help test the PublicDispatchDataSourceView view."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
        database=database,
    )
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    builder_to = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(builder=builder, published_to=builder_to)
    public_page = data_fixture.create_builder_page(builder=builder_to)

    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )

    page = data_fixture.create_builder_page(user=user, builder=builder)

    return {
        "user": user,
        "token": token,
        "page": page,
        "public_page": public_page,
        "integration": integration,
        "table": table,
        "rows": rows,
        "fields": fields,
        "builder_to": builder_to,
    }


@pytest.fixture
def data_source_element_roles_fixture(data_fixture):
    """
    A fixture to help test the DispatchDataSourcesView view using Elements
    and user roles.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(builder=builder, published_to=builder_to)
    public_page = data_fixture.create_builder_page(builder=builder_to)

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("Color", "text"),
        ],
        rows=[
            ["Apple", "Red"],
            ["Banana", "Yellow"],
            ["Cherry", "Purple"],
        ],
    )

    return {
        "page": public_page,
        "user": user,
        "table": table,
        "fields": fields,
        "rows": rows,
        "builder_to": builder_to,
    }


@pytest.mark.django_db
def test_dispatch_data_sources_list_rows_no_elements(
    api_client, data_fixture, data_source_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    If the page has zero elements, the API response should not contain any
    field specific data.
    """

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['token']}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": [],
        },
    }


@pytest.mark.django_db
def test_dispatch_data_sources_get_row_no_elements(
    api_client, data_fixture, data_source_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of Get Row.

    If the page has zero elements, the API response should not contain any
    field specific data.
    """

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
        row_id="2",
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['token']}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {str(data_source.id): {}}


@pytest.mark.django_db
def test_dispatch_data_sources_list_rows_with_elements(
    api_client, data_fixture, data_source_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    The API response should only contain field data when the field is
    referenced in an element via a formula.
    """

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
    )

    field = data_source_fixture["fields"][0]
    field_id = field.id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.field_{field_id}')"},
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['token']}",
    )

    expected_results = [
        {field.name: getattr(row, f"field_{field_id}"), "id": row.id}
        for row in data_source_fixture["rows"]
    ]

    assert response.status_code == HTTP_200_OK
    # Although this Data Source has 2 Fields/Columns, only one is returned
    # since only one field_id is used by the Table.
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": expected_results,
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    # table_row_id is 1-indexed to reflect the row ID in formulas
    # db_row_id is 0-indexed to reflect the row ID in the database
    "table_row_id,db_row_id,",
    [
        (1, 0),
        (2, 1),
        (3, 2),
    ],
)
def test_dispatch_data_sources_get_row_with_elements(
    api_client, data_fixture, data_source_fixture, table_row_id, db_row_id
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of Get Row.

    The API response should only contain field data when the field is
    referenced in an element via a formula.
    """

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
        row_id=table_row_id,
    )

    field_id = data_source_fixture["fields"][0].id

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {
                    "value": f"get('data_source.{data_source.id}.field_{field_id}')"
                },
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['token']}",
    )

    rows = data_source_fixture["rows"]
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            data_source_fixture["fields"][0].name: getattr(
                rows[db_row_id], f"field_{field_id}"
            ),
            "id": rows[db_row_id].id,
        }
    }


@pytest.mark.django_db
def test_dispatch_data_sources_get_and_list_rows_with_elements(
    api_client,
    data_fixture,
    data_source_fixture,
):
    """
    Test the DispatchDataSourcesView endpoint when using a mix of Data Source
    types, i.e. Get Row and List Rows.

    The API response should only contain field data when the field is
    referenced in an element via a formula.
    """

    user = data_source_fixture["user"]
    table_1, fields_1, rows_1 = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
        ],
        rows=[
            ["Palak Paneer", "Paneer Pakora"],
        ],
    )
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=data_source_fixture["user"],
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=table_1,
        row_id=1,
    )

    table_2, fields_2, rows_2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Fruits", "text"),
        ],
        rows=[
            ["Kiwi", "Cherry"],
        ],
    )
    data_source_2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=data_source_fixture["page"],
        integration=data_source_fixture["integration"],
        table=table_2,
    )

    # Create an element that uses a concatenation of two "get" formulas; one
    # using the Get Row and the other using List Row data sources.
    formula = (
        f"concat(get('current_record.field_{fields_1[0].id}'),"
        f"get('data_source.{data_source_1.id}.field_{fields_1[0].id}'))"
    )
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source_1,
        fields=[
            {
                "name": "My Dishes",
                "type": "text",
                "config": {"value": formula},
            },
        ],
    )

    # Create another table, this time using the List Row data source
    data_fixture.create_builder_table_element(
        page=data_source_fixture["page"],
        data_source=data_source_2,
        fields=[
            {
                "name": "My Fruits",
                "type": "text",
                "config": {"value": f"get('current_record.field_{fields_2[0].id}')"},
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": data_source_fixture["page"].id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {data_source_fixture['token']}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source_1.id): {
            fields_1[0].name: getattr(rows_1[0], f"field_{fields_1[0].id}"),
            "id": rows_1[0].id,
        },
        # Although this Data Source has 2 Fields/Columns, only one is returned
        # since only one field_id is used by the Table.
        str(data_source_2.id): {
            "has_next_page": False,
            "results": [
                {
                    fields_2[0].name: getattr(rows_2[0], f"field_{fields_2[0].id}"),
                    "id": rows_2[0].id,
                },
            ],
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,element_role,expect_fields",
    [
        # When the user role doesn't match the Element's role,
        # the fields should *not* be returned.
        ("foo_role", "bar_role", False),
        # When the user and Element roles match, the fields should
        # be returned.
        ("foo_role", "foo_role", True),
    ],
)
def test_dispatch_data_sources_list_rows_with_elements_and_role(
    api_client,
    data_fixture,
    data_source_element_roles_fixture,
    user_role,
    element_role,
    expect_fields,
):
    """
    Test the DispatchDataSourcesView endpoint when using a Data Source type
    of List Rows.

    This test creates a Element with a role. Depending on whether expect_fields
    is True or False, the test checks to see if the Data Source view returns
    the fields.

    The API response should only contain field data when the field is
    referenced in an element via a formula, and that element is visible
    to the user.
    """

    page = data_source_element_roles_fixture["page"]

    user_source, integration = data_fixture.create_user_table_and_role(
        data_source_element_roles_fixture["user"],
        data_source_element_roles_fixture["builder_to"],
        user_role,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com"
    )
    token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_element_roles_fixture["user"],
        page=page,
        integration=integration,
        table=data_source_element_roles_fixture["table"],
    )

    field = data_source_element_roles_fixture["fields"][0]
    field_id = field.id
    field_name = f"field_{field_id}"

    # Create an element that uses a formula referencing the data source
    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        visibility=Element.VISIBILITY_TYPES.LOGGED_IN,
        roles=[element_role],
        role_type=Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
        fields=[
            {
                "name": "FieldA",
                "type": "text",
                "config": {"value": f"get('current_record.{field_name}')"},
            },
        ],
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    expected_results = []
    for row in data_source_element_roles_fixture["rows"]:
        if expect_fields:
            # Field should only be visible if the user's role allows them
            # to see the data source fields.

            expected_results.append(
                {field.name: getattr(row, field_name), "id": row.id}
            )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": expected_results,
        },
    }


@pytest.mark.django_db
def test_dispatch_data_sources_page_visibility_all_returns_elements(
    api_client, data_fixture, data_source_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when the Page visibility allows
    access to the user.

    If the page's visibility is set to 'all' and the user is anonymous, the
    endpoint should return elements.
    """

    page = data_source_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.ALL
    page.save()

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_fixture["user"],
        page=page,
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
    )

    # Create an element containing a formula
    field = data_source_fixture["fields"][0]
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.0.field_{field.id}')",
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(url, {}, format="json")

    # Since Page visiblity is 'all', the response should contain the resolved
    # formula even if the user is not logged in.
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": [
                {field.name: "Apple"},
                {field.name: "Banana"},
                {field.name: "Cherry"},
            ],
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles",
    [
        [],
        ["foo_role"],
    ],
)
def test_dispatch_data_sources_page_visibility_logged_in_allow_all_returns_elements(
    api_client, data_fixture, data_source_fixture, roles
):
    """
    Test the DispatchDataSourcesView endpoint when the Page visibility allows
    access to the user.

    If the page's visibility is set to 'logged-in' and the role_type is set to
    'allow_all', the endpoint should return elements regardless of the user's
    current role.
    """

    page = data_source_fixture["public_page"]
    page.visibility = Page.VISIBILITY_TYPES.LOGGED_IN
    page.role_type = Page.ROLE_TYPES.ALLOW_ALL
    page.roles = roles
    page.save()

    integration = data_source_fixture["integration"]
    user = data_source_fixture["user"]
    user_source, _ = data_fixture.create_user_table_and_role(
        user,
        data_source_fixture["builder_to"],
        "foo_role",
        integration=integration,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com"
    )
    user_token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_fixture["user"],
        page=page,
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
    )

    # Create an element containing a formula
    field = data_source_fixture["fields"][0]
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.0.field_{field.id}')",
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {user_token}"
    )

    # Since the request was made with an anonymous user and the Page visiblity
    # is 'logged-in', the response should *not* contain any resolved formulas.
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": [
                {field.name: "Apple"},
                {field.name: "Banana"},
                {field.name: "Cherry"},
            ],
        },
    }


@pytest.mark.django_db
def test_dispatch_data_sources_page_visibility_logged_in_returns_no_elements_for_anon(
    api_client, data_fixture, data_source_fixture
):
    """
    Test the DispatchDataSourcesView endpoint when the Page visibility denies
    access to the user.

    If the page's visibility is set to 'logged-in' and the user is anonymous, the
    endpoint should return zero elements.
    """

    page = data_source_fixture["page"]
    page.visibility = Page.VISIBILITY_TYPES.LOGGED_IN
    page.save()

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=data_source_fixture["user"],
        page=page,
        integration=data_source_fixture["integration"],
        table=data_source_fixture["table"],
    )

    # Create an element containing a formula
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.0.field_{data_source_fixture['fields'][0].id}')",
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(url, {}, format="json")

    # Since the request was made with an anonymous user and the Page visibility
    # is 'logged-in', the response should *not* contain any resolved formulas.
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": [],
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_role,role_type,roles,is_allowed",
    [
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            [],
            # Allowed because "foo_role" isn't excluded
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["bar_role"],
            # Allowed because "foo_role" isn't excluded
            True,
        ),
        (
            "",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["bar_role"],
            # Allowed because "" isn't excluded
            True,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            ["foo_role"],
            # Disallowed because "foo_role" is excluded
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            # Allowed because "foo_role" isn't excluded
            True,
        ),
        (
            "",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            # Disallowed because "" isn't excluded
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            [],
            # Disallowed because "foo_role" isn't excluded
            False,
        ),
        (
            "foo_role",
            Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
            ["foo_role"],
            # Allowed because "foo_role" is excluded
            True,
        ),
    ],
)
def test_dispatch_data_sources_page_visibility_logged_in_allow_all_except(
    api_client,
    data_fixture,
    data_source_fixture,
    user_role,
    role_type,
    roles,
    is_allowed,
):
    """
    Test the DispatchDataSourcesView endpoint when the Page visibility allows
    access to the user.

    If the page's visibility is set to 'logged-in' and the role_type is set to
    'allow_all', the endpoint should return elements regardless of the user's
    current role.
    """

    page = data_source_fixture["public_page"]
    page.visibility = Page.VISIBILITY_TYPES.LOGGED_IN
    page.role_type = role_type
    page.roles = roles
    page.save()

    integration = data_source_fixture["integration"]
    user = data_source_fixture["user"]
    user_source, _ = data_fixture.create_user_table_and_role(
        user,
        data_source_fixture["builder_to"],
        user_role,
        integration=integration,
    )
    user_source_user = UserSourceUser(
        user_source, None, 1, "foo_username", "foo@bar.com"
    )
    user_token = user_source_user.get_refresh_token().access_token

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=data_source_fixture["table"],
    )

    # Create an element containing a formula
    field = data_source_fixture["fields"][0]
    data_fixture.create_builder_heading_element(
        page=page,
        value=f"get('data_source.{data_source.id}.0.field_{field.id}')",
    )

    url = reverse(
        "api:builder:domains:public_dispatch_all",
        kwargs={"page_id": page.id},
    )

    response = api_client.post(
        url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {user_token}"
    )

    assert response.status_code == HTTP_200_OK

    if is_allowed:
        expected_results = [
            {field.name: "Apple"},
            {field.name: "Banana"},
            {field.name: "Cherry"},
        ]
    else:
        expected_results = []

    assert response.json() == {
        str(data_source.id): {
            "has_next_page": False,
            "results": expected_results,
        },
    }
