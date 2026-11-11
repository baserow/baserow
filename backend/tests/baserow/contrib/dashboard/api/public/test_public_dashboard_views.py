import pytest
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.handler import CoreHandler

PASSWORD = "12345678"  # nosec b105


def public_info_url(slug):
    return reverse("api:dashboard:public:info", kwargs={"slug": slug})


def public_auth_url(slug):
    return reverse("api:dashboard:public:auth", kwargs={"slug": slug})


def public_dispatch_url(slug, data_source_id):
    return reverse(
        "api:dashboard:public:data_source_dispatch",
        kwargs={"slug": slug, "data_source_id": data_source_id},
    )


def authenticated_dispatch_url(data_source_id):
    return reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": data_source_id},
    )


def sharing_url(dashboard):
    return reverse("api:dashboard:sharing", kwargs={"dashboard_id": dashboard.id})


def create_shared_dashboard(data_fixture, user, workspace=None, **dashboard_kwargs):
    """
    Creates a dashboard with one summary widget that sums a number field of a
    table in the same workspace. The rows sum to 60.
    """

    if workspace is None:
        workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table, name="Amount")
    RowHandler().create_rows(
        user,
        table,
        [
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 20},
            {f"field_{field.id}": 30},
        ],
    )
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace,
        name="Sales",
        description="Numbers of the quarter",
        **dashboard_kwargs,
    )
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        integration=integration, table=table, field=field, aggregation_type="sum"
    )
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Sum of amount", user=user, dashboard=dashboard, service=service
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard,
        data_source=data_source,
        title="Total",
        description="All amounts",
    )
    return dashboard, data_source, widget


def protect_with_password(dashboard, password=PASSWORD):
    dashboard.set_password(password)
    dashboard.save()


def get_public_access_token(api_client, slug, password=PASSWORD):
    response = api_client.post(
        public_auth_url(slug), {"password": password}, format="json"
    )
    assert response.status_code == HTTP_200_OK, response.json()
    return response.json()["access_token"]


@pytest.mark.django_db
def test_get_public_dashboard_info(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard, data_source, widget = create_shared_dashboard(
        data_fixture, user, public=True
    )

    response = api_client.get(public_info_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["dashboard"] == {
        "id": dashboard.id,
        "name": "Sales",
        "description": "Numbers of the quarter",
        "show_logo": True,
    }

    assert len(response_json["widgets"]) == 1
    public_widget = response_json["widgets"][0]
    assert public_widget["id"] == widget.id
    assert public_widget["type"] == "summary"
    assert public_widget["title"] == "Total"
    assert public_widget["data_source_id"] == data_source.id

    assert len(response_json["data_sources"]) == 1
    public_data_source = response_json["data_sources"][0]
    assert public_data_source["id"] == data_source.id
    assert public_data_source["name"] == "Sum of amount"
    assert public_data_source["type"] == "local_baserow_aggregate_rows"
    assert "result" in public_data_source["schema"]["properties"]
    assert public_data_source["context_data"]["field"]["name"] == "Amount"
    # The summary widget formats the result with the aggregation type.
    assert public_data_source["aggregation_type"] == "sum"


@pytest.mark.django_db
def test_get_public_dashboard_info_never_exposes_the_sharing_or_service_config(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    dashboard, data_source, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)
    token = get_public_access_token(api_client, dashboard.slug)

    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert set(response_json["dashboard"].keys()) == {
        "id",
        "name",
        "description",
        "show_logo",
    }
    assert "slug" not in response.content.decode()
    assert dashboard.public_password not in response.content.decode()

    public_data_source = response_json["data_sources"][0]
    # `table_id` is part of the public contract of every table service type, but
    # visitors get the placeholder, and the summary widget needs the
    # `aggregation_type` to format the result. The rest of the service
    # configuration must stay private.
    assert set(public_data_source.keys()) == {
        "id",
        "name",
        "type",
        "schema",
        "context_data",
        "table_id",
        "aggregation_type",
    }
    assert public_data_source["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    # The field is reduced to what the widget needs to format the result.
    public_field = public_data_source["context_data"]["field"]
    assert set(public_field.keys()) == {
        "id",
        "table_id",
        "name",
        "type",
        "primary",
        "read_only",
        "database_id",
        "workspace_id",
        "number_decimal_places",
        "number_negative",
        "number_prefix",
        "number_suffix",
        "number_separator",
    }
    assert public_field["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert public_field["database_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert public_field["workspace_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    for private_key in (
        "integration_id",
        "view_id",
        "field_id",
        "filters",
        "filter_type",
        "search_query",
        "dashboard_id",
        "order",
        "sample_data",
        "context_data_schema",
    ):
        assert private_key not in public_data_source


@pytest.mark.django_db
def test_get_public_dashboard_info_never_exposes_the_configuration_of_the_field(
    api_client, data_fixture
):
    user = data_fixture.create_user(first_name="Hidden collaborator")
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_created_by_field(table=table, name="Author")
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, public=True
    )
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        integration=integration,
        table=table,
        field=field,
        aggregation_type="empty_count",
    )
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Authors", user=user, dashboard=dashboard, service=service
        )
    )
    data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source, title="Authors"
    )

    response = api_client.get(public_info_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_200_OK
    public_field = response.json()["data_sources"][0]["context_data"]["field"]
    assert public_field == {
        "id": field.id,
        "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "name": "Author",
        "type": "created_by",
        "primary": False,
        "read_only": True,
        "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
    }
    body = response.content.decode()
    assert "available_collaborators" not in body
    assert "Hidden collaborator" not in body


@pytest.mark.django_db
def test_get_public_dashboard_info_private_dashboard_is_not_found_for_visitors(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=False)

    response = api_client.get(public_info_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_dashboard_info_private_dashboard_for_a_workspace_member(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=False)

    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["dashboard"]["id"] == dashboard.id


@pytest.mark.django_db
def test_get_public_dashboard_info_private_dashboard_for_a_user_of_another_workspace(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    _, other_token = data_fixture.create_user_and_token()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=False)

    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_dashboard_info_unknown_slug(api_client, data_fixture):
    response = api_client.get(public_info_url("does-not-exist"), format="json")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_dashboard_info_trashed_dashboard(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=True)
    CoreHandler().delete_application(user, dashboard)

    response = api_client.get(public_info_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_dashboard_info_trashed_workspace(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard, _, _ = create_shared_dashboard(
        data_fixture, user, workspace=workspace, public=True
    )
    CoreHandler().delete_workspace_by_id(user, workspace.id)

    response = api_client.get(public_info_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_dashboard_info_password_protected(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    _, other_token = data_fixture.create_user_and_token()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)

    # Visitors without a token are asked for the password.
    response = api_client.get(public_info_url(dashboard.slug), format="json")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD"

    # An invalid token is as good as no token.
    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION="JWT invalid-token",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD"

    # A logged in user of another workspace needs the password too.
    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # Members of the workspace never see the password page.
    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    # The token handed out for the password opens the dashboard.
    access_token = get_public_access_token(api_client, dashboard.slug)
    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {access_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["dashboard"]["id"] == dashboard.id


@pytest.mark.django_db
def test_public_dashboard_auth_with_a_wrong_password(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)

    response = api_client.post(
        public_auth_url(dashboard.slug), {"password": "wrong-password"}, format="json"
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_public_dashboard_auth_of_a_private_dashboard(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=False)
    protect_with_password(dashboard)

    response = api_client.post(
        public_auth_url(dashboard.slug), {"password": PASSWORD}, format="json"
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_public_dashboard_auth_info(api_client, data_fixture):
    user = data_fixture.create_user()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)

    # The password page follows the logo choice of the owner, without a token.
    response = api_client.get(public_auth_url(dashboard.slug), format="json")
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"show_logo": True}

    dashboard.show_logo = False
    dashboard.save()

    response = api_client.get(public_auth_url(dashboard.slug), format="json")
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"show_logo": False}


@pytest.mark.django_db
def test_get_public_dashboard_auth_info_of_a_private_dashboard(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=False)
    protect_with_password(dashboard)

    response = api_client.get(public_auth_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"

    response = api_client.get(public_auth_url("unknown-slug"), format="json")

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_rotating_the_slug_invalidates_public_dashboard_tokens(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)
    access_token = get_public_access_token(api_client, dashboard.slug)

    response = api_client.post(
        reverse("api:dashboard:rotate_slug", kwargs={"dashboard_id": dashboard.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    new_slug = response.json()["slug"]
    assert new_slug != dashboard.slug

    response = api_client.get(
        public_info_url(new_slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {access_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    new_access_token = get_public_access_token(api_client, new_slug)
    response = api_client.get(
        public_info_url(new_slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {new_access_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_changing_the_password_invalidates_public_dashboard_tokens(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard, _, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)
    access_token = get_public_access_token(api_client, dashboard.slug)

    response = api_client.patch(
        sharing_url(dashboard),
        {"public_password": "new-password"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {access_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    new_access_token = get_public_access_token(
        api_client, dashboard.slug, password="new-password"
    )
    response = api_client.get(
        public_info_url(dashboard.slug),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {new_access_token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_dispatch_public_dashboard_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    dashboard, data_source, _ = create_shared_dashboard(data_fixture, user, public=True)

    response = api_client.post(
        public_dispatch_url(dashboard.slug, data_source.id), format="json"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"result": "60"}

    # Visitors get exactly what a member gets.
    authenticated_response = api_client.post(
        authenticated_dispatch_url(data_source.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert authenticated_response.status_code == HTTP_200_OK
    assert response.json() == authenticated_response.json()


@pytest.mark.django_db
def test_dispatch_public_dashboard_data_source_of_another_dashboard(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard, _, _ = create_shared_dashboard(
        data_fixture, user, workspace=workspace, public=True
    )
    _, other_data_source, _ = create_shared_dashboard(
        data_fixture, user, workspace=workspace, public=True
    )

    response = api_client.post(
        public_dispatch_url(dashboard.slug, other_data_source.id), format="json"
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_dispatch_public_dashboard_data_source_of_a_private_dashboard(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    dashboard, data_source, _ = create_shared_dashboard(
        data_fixture, user, public=False
    )

    response = api_client.post(
        public_dispatch_url(dashboard.slug, data_source.id), format="json"
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DASHBOARD_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_dispatch_public_dashboard_data_source_password_protected(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    dashboard, data_source, _ = create_shared_dashboard(data_fixture, user, public=True)
    protect_with_password(dashboard)

    response = api_client.post(
        public_dispatch_url(dashboard.slug, data_source.id), format="json"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD"

    access_token = get_public_access_token(api_client, dashboard.slug)
    response = api_client.post(
        public_dispatch_url(dashboard.slug, data_source.id),
        format="json",
        HTTP_BASEROW_DASHBOARD_AUTHORIZATION=f"JWT {access_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"result": "60"}
