from django.test.utils import override_settings

import pytest
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
)

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("view_type", view_type_registry.registry.keys())
def test_premium_view_attributes_view(view_type, api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    view = ViewHandler().create_view(
        user=user, table=table, type_name=view_type, name=view_type
    )

    response = api_client.patch(
        reverse(
            "api:premium:view:premium_view_attributes", kwargs={"view_id": view.id}
        ),
        data={"show_logo": False},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_logo"] is False
    assert response_json["allow_public_export"] is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("view_type", view_type_registry.registry.keys())
def test_premium_view_attributes_view_allow_public_export(
    view_type, api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    view = ViewHandler().create_view(
        user=user, table=table, type_name=view_type, name=view_type
    )

    response = api_client.patch(
        reverse(
            "api:premium:view:premium_view_attributes", kwargs={"view_id": view.id}
        ),
        data={"allow_public_export": True},
        format="json",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["show_logo"] is True
    assert response_json["allow_public_export"] is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_view_attributes_as_non_premium_user(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=False
    )
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    view = premium_data_fixture.create_grid_view(table=table)

    response = api_client.patch(
        reverse(
            "api:premium:view:premium_view_attributes", kwargs={"view_id": view.id}
        ),
        {"show_logo": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_view_attributes_invalid_attributes(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    view = premium_data_fixture.create_grid_view(table=table, name="some name")

    response = api_client.patch(
        reverse(
            "api:premium:view:premium_view_attributes", kwargs={"view_id": view.id}
        ),
        {"name": "some new name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "some name"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_view_attributes_template(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    view = premium_data_fixture.create_grid_view(table=table, name="some name")
    premium_data_fixture.create_template(workspace=workspace)

    response = api_client.patch(
        reverse(
            "api:premium:view:premium_view_attributes", kwargs={"view_id": view.id}
        ),
        {"name": "some new name"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"] == "ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE"
    )
