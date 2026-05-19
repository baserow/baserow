from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.integrations.models import Integration


@pytest.mark.django_db
def test_get_integrations(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application, authorized_user=user
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application, authorized_user=user
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application, authorized_user=user
    )
    data_fixture.create_local_baserow_integration()

    url = reverse("api:integrations:list", kwargs={"application_id": application.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["id"] == integration1.id
    assert response_json[0]["type"] == "local_baserow"
    assert response_json[0]["context_data"]["databases"][0]["id"] == database.id
    assert "authorized_user" in response_json[0]
    assert response_json[1]["id"] == integration2.id
    assert response_json[1]["type"] == "local_baserow"
    assert response_json[1]["context_data"]["databases"][0]["id"] == database.id
    assert response_json[2]["id"] == integration3.id
    assert response_json[2]["type"] == "local_baserow"
    assert response_json[2]["context_data"]["databases"][0]["id"] == database.id


@pytest.mark.django_db
def test_create_integration(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    data_fixture.create_database_table(database=database)

    url = reverse("api:integrations:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {"type": "local_baserow", "name": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "local_baserow"
    assert response_json["authorized_user"]["username"] == user.username
    assert response_json["context_data"]["databases"][0]["id"] == database.id

    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "authorized_user_id": 17,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["authorized_user"]["username"] == user.username


@pytest.mark.django_db
def test_create_integration_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)

    url = reverse("api:integrations:list", kwargs={"application_id": application.id})
    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.post(
            url,
            {"type": "local_baserow", "name": "test"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_integration_application_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:integrations:list", kwargs={"application_id": 0})
    response = api_client.post(
        url,
        {"type": "local_baserow", "name": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_integration_bad_application_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_database_application(user=user)

    url = reverse("api:integrations:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {"type": "local_baserow", "name": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED"


@pytest.mark.django_db
def test_update_integration(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:item", kwargs={"integration_id": integration1.id})
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["authorized_user"]["username"] == user.username


@pytest.mark.django_db
@pytest.mark.skip  # No modifiable integration yet
def test_update_integration_bad_request(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:item", kwargs={"integration_id": integration1.id})
    response = api_client.patch(
        url,
        {"modifiable_field": []},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_update_integration_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:integrations:item", kwargs={"integration_id": 0})
    response = api_client.patch(
        url,
        {"value": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_INTEGRATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_move_integration_empty_payload(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:move", kwargs={"integration_id": integration1.id})
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert Integration.objects.last().id == integration1.id


@pytest.mark.django_db
def test_move_integration_null_before_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:move", kwargs={"integration_id": integration1.id})
    response = api_client.patch(
        url,
        {"before_id": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert Integration.objects.last().id == integration1.id


@pytest.mark.django_db
def test_move_integration_before(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:move", kwargs={"integration_id": integration3.id})
    response = api_client.patch(
        url,
        {"before_id": integration2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == integration3.id

    assert list(Integration.objects.all())[1].id == integration3.id


@pytest.mark.django_db
def test_move_integration_before_not_in_same_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    application2 = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration2 = data_fixture.create_local_baserow_integration(
        application=application
    )
    integration3 = data_fixture.create_local_baserow_integration(
        application=application2
    )

    url = reverse("api:integrations:move", kwargs={"integration_id": integration3.id})
    response = api_client.patch(
        url,
        {"before_id": integration2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INTEGRATION_NOT_IN_SAME_APPLICATION"


@pytest.mark.django_db
def test_move_integration_bad_before_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:move", kwargs={"integration_id": integration1.id})
    response = api_client.patch(
        url,
        {"before_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_integration(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:item", kwargs={"integration_id": integration1.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_integration_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration1 = data_fixture.create_local_baserow_integration(
        application=application
    )

    url = reverse("api:integrations:item", kwargs={"integration_id": integration1.id})

    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.delete(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_integration_integration_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:integrations:item", kwargs={"integration_id": 0})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_INTEGRATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_integrations_context_data_present_when_databases_raises(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    data_fixture.create_local_baserow_integration(
        application=application, authorized_user=user
    )

    with patch(
        "baserow.contrib.integrations.local_baserow.integration_types"
        ".LocalBaserowIntegrationType.get_local_baserow_databases",
        side_effect=AttributeError("simulated failure"),
    ):
        url = reverse(
            "api:integrations:list", kwargs={"application_id": application.id}
        )
        response = api_client.get(url, format="json", HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[0]["context_data"] == {"databases": []}
