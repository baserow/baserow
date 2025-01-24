from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.app_auth_providers.models import AppAuthProvider
from baserow.core.app_auth_providers.registries import app_auth_provider_type_registry
from baserow.core.user_sources.models import UserSource


@pytest.mark.django_db
def test_get_user_sources(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    data_fixture.create_user_source_with_first_type()

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["id"] == user_source1.id
    assert response_json[0]["type"] == "local_baserow"
    assert response_json[1]["id"] == user_source2.id
    assert response_json[1]["type"] == "local_baserow"
    assert response_json[2]["id"] == user_source3.id
    assert response_json[2]["type"] == "local_baserow"


@pytest.mark.django_db
def test_get_user_sources_w_auth_providers(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    app_auth_provider1 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source1, domain="A"
    )
    app_auth_provider2 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source2, domain="A"
    )

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 3
    assert response_json[0]["id"] == user_source1.id
    assert response_json[0]["type"] == "local_baserow"
    assert response_json[0]["auth_providers"] == [
        {
            "domain": "A",
            "id": app_auth_provider1.id,
            "password_field_id": None,
            "type": app_auth_provider1.get_type().type,
        },
    ]
    assert response_json[1]["id"] == user_source2.id
    assert response_json[1]["type"] == "local_baserow"
    assert response_json[1]["auth_providers"] == [
        {
            "domain": "A",
            "id": app_auth_provider2.id,
            "password_field_id": None,
            "type": app_auth_provider2.get_type().type,
        },
    ]
    assert response_json[2]["id"] == user_source3.id
    assert response_json[2]["type"] == "local_baserow"
    assert response_json[2]["auth_providers"] == []


@pytest.mark.django_db
def test_create_user_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {"type": "local_baserow", "name": "test", "integration_id": integration.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "local_baserow"
    assert response_json["user_count"] is None
    assert response_json["user_count_updated_at"] is None


@pytest.mark.django_db
def test_create_user_source_missing_properties(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {"type": "local_baserow", "integration_id": integration.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_user_source_missing_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {"type": "missing_type", "name": "test", "integration_id": integration.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_user_source_w_auth_providers(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "enabled": False,
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert AppAuthProvider.objects.count() == 1
    first = AppAuthProvider.objects.first()

    assert response_json["auth_providers"] == [
        {
            "id": first.id,
            "password_field_id": None,
            "type": "local_baserow_password",
            "domain": None,
        },
    ]


@pytest.mark.django_db
def test_create_user_source_w_auth_providers_w_domain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "auth_providers": [
                {
                    "domain": "domain.com",
                    "type": "local_baserow_password",
                    "enabled": False,
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK

    assert AppAuthProvider.objects.count() == 1
    first = AppAuthProvider.objects.first()

    assert response_json["auth_providers"] == [
        {
            "id": first.id,
            "password_field_id": None,
            "type": "local_baserow_password",
            "domain": "domain.com",
        },
    ]


@pytest.mark.django_db
def test_create_user_source_w_auth_providers_w_wrong_domain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "auth_providers": [
                {
                    "domain": "baddomain",
                    "type": "local_baserow_password",
                    "enabled": False,
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_user_source_w_auth_provider_wrong_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    app_auth_provider_type = list(app_auth_provider_type_registry.get_all())[0]

    original_compatible = app_auth_provider_type.compatible_user_source_types
    app_auth_provider_type.compatible_user_source_types = []

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "auth_providers": [
                {
                    "enabled": True,
                    "type": app_auth_provider_type.type,
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    app_auth_provider_type.compatible_user_source_types = original_compatible

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_AUTH_PROVIDER_TYPE_NOT_COMPATIBLE"


@pytest.mark.django_db
def test_create_user_source_w_auth_provider_missing_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {
            "type": "local_baserow",
            "name": "test",
            "integration_id": integration.id,
            "auth_providers": [
                {
                    "enabled": True,
                    "type": "bad_type",
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_AUTH_PROVIDER_TYPE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_user_source_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.post(
            url,
            {"type": "local_baserow", "name": "test", "integration_id": integration.id},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_user_source_application_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:user_sources:list", kwargs={"application_id": 0})
    response = api_client.post(
        url,
        {"type": "local_baserow", "name": "test", "integration_id": 42},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_user_source_bad_application_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_database_application(user=user)
    integration = data_fixture.create_local_baserow_integration(application=application)

    url = reverse("api:user_sources:list", kwargs={"application_id": application.id})
    response = api_client.post(
        url,
        {"type": "local_baserow", "name": "test", "integration_id": integration.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED"


@pytest.mark.django_db
def test_update_user_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    integration = data_fixture.create_local_baserow_integration(
        application=application, authorized_user=user
    )

    url = reverse("api:user_sources:item", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {"integration_id": integration.id, "name": "newName"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "newName"
    assert response_json["integration_id"] == integration.id
    assert response_json["user_count"] is None
    assert response_json["user_count_updated_at"] is None

    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    name_field = data_fixture.create_text_field(table=table)
    email_field = data_fixture.create_email_field(table=table)
    model = table.get_model(field_ids=[])
    model.objects.create()
    model.objects.create()
    model.objects.create()

    response = api_client.patch(
        url,
        {
            "table_id": table.id,
            "name_field_id": name_field.id,
            "email_field_id": email_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["user_count"] == 3
    assert response_json["user_count_updated_at"] is not None


@pytest.mark.django_db
def test_update_user_source_w_auth_providers(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:item", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "enabled": False,
                    "domain": "test2.com",
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK

    assert AppAuthProvider.objects.count() == 1
    first = AppAuthProvider.objects.first()

    assert response.json()["auth_providers"] == [
        {
            "domain": "test2.com",
            "id": first.id,
            "password_field_id": None,
            "type": "local_baserow_password",
        },
    ]

    response = api_client.patch(
        url,
        {
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "enabled": False,
                    "domain": "test3.com",
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert AppAuthProvider.objects.count() == 1
    first = AppAuthProvider.objects.first()

    assert response.json()["auth_providers"] == [
        {
            "domain": "test3.com",
            "id": first.id,
            "password_field_id": None,
            "type": "local_baserow_password",
        },
    ]


@pytest.mark.django_db
def test_update_user_source_with_bad_auth_providers(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:item", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "enabled": [],
                    "domain": [],
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST

    response = api_client.patch(
        url,
        {
            "auth_providers": [
                {
                    "type": "local_baserow_password",
                    "password_field_id": [],
                },
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_update_user_source_w_missing_auth_provider_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:item", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {
            "auth_providers": [
                {"type": "missing", "enabled": False, "domain": "test1"},
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_AUTH_PROVIDER_TYPE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_user_source_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:user_sources:item", kwargs={"user_source_id": 0})
    response = api_client.patch(
        url,
        {"value": "test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_USER_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_move_user_source_empty_payload(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:move", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert UserSource.objects.last().id == user_source1.id


@pytest.mark.django_db
def test_move_user_source_null_before_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:move", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {"before_id": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    assert UserSource.objects.last().id == user_source1.id


@pytest.mark.django_db
def test_move_user_source_before(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:move", kwargs={"user_source_id": user_source3.id})
    response = api_client.patch(
        url,
        {"before_id": user_source2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == user_source3.id

    assert list(UserSource.objects.all())[1].id == user_source3.id


@pytest.mark.django_db
def test_move_user_source_before_not_in_same_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    application2 = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=application2
    )

    url = reverse("api:user_sources:move", kwargs={"user_source_id": user_source3.id})
    response = api_client.patch(
        url,
        {"before_id": user_source2.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_SOURCE_NOT_IN_SAME_APPLICATION"


@pytest.mark.django_db
def test_move_user_source_bad_before_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:move", kwargs={"user_source_id": user_source1.id})
    response = api_client.patch(
        url,
        {"before_id": 9999},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_user_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:item", kwargs={"user_source_id": user_source1.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_user_source_permission_denied(
    api_client, data_fixture, stub_check_permissions
):
    user, token = data_fixture.create_user_and_token()
    application = data_fixture.create_builder_application(user=user)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse("api:user_sources:item", kwargs={"user_source_id": user_source1.id})

    with stub_check_permissions(raise_permission_denied=True):
        response = api_client.delete(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_user_source_user_source_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:user_sources:item", kwargs={"user_source_id": 0})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_USER_SOURCE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_get_user_source_users(api_client, data_fixture, stub_user_source_registry):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    def list_users_return(user_source, count, search):
        if user_source.id == user_source1.id:
            return [
                data_fixture.create_user_source_user(
                    user_source=user_source,
                    user_id=1,
                    email="test1@mail.com",
                    username="user1",
                ),
                data_fixture.create_user_source_user(
                    user_source=user_source,
                    user_id=2,
                    email="test2@mail.com",
                    username="user2",
                ),
            ]
        if user_source.id == user_source2.id:
            return [
                data_fixture.create_user_source_user(
                    user_source=user_source,
                    user_id=3,
                    email="test3@mail.com",
                    username="user3",
                ),
            ]
        return []

    url = reverse(
        "api:user_sources:list_user_source_users",
        kwargs={"application_id": application.id},
    )
    with stub_user_source_registry(list_users_return=list_users_return):
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "users_per_user_sources" in response_json
    assert response_json["users_per_user_sources"] == {
        str(user_source1.id): [
            {
                "id": 1,
                "role": "",
                "email": "test1@mail.com",
                "username": "user1",
                "user_source_id": user_source1.id,
            },
            {
                "id": 2,
                "role": "",
                "email": "test2@mail.com",
                "username": "user2",
                "user_source_id": user_source1.id,
            },
        ],
        str(user_source2.id): [
            {
                "id": 3,
                "role": "",
                "email": "test3@mail.com",
                "username": "user3",
                "user_source_id": user_source2.id,
            }
        ],
    }


@pytest.mark.django_db
def test_get_user_source_users_with_search(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    def list_users_return(user_source, count, search):
        if search == "first":
            if user_source.id == user_source1.id:
                return [
                    data_fixture.create_user_source_user(
                        user_source=user_source,
                        user_id=1,
                        email="test1@mail.com",
                        username="user1",
                    ),
                    data_fixture.create_user_source_user(
                        user_source=user_source,
                        user_id=2,
                        email="test2@mail.com",
                        username="user2",
                    ),
                ]
        if search == "second":
            if user_source.id == user_source2.id:
                return [
                    data_fixture.create_user_source_user(
                        user_source=user_source,
                        user_id=3,
                        email="test3@mail.com",
                        username="user3",
                    ),
                ]
        return []

    url = reverse(
        "api:user_sources:list_user_source_users",
        kwargs={"application_id": application.id},
    )
    with stub_user_source_registry(list_users_return=list_users_return):
        response = api_client.get(
            url,
            {"search": "first"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "users_per_user_sources" in response_json
    assert response_json["users_per_user_sources"] == {
        str(user_source1.id): [
            {
                "id": 1,
                "role": "",
                "email": "test1@mail.com",
                "username": "user1",
                "user_source_id": user_source1.id,
            },
            {
                "id": 2,
                "role": "",
                "email": "test2@mail.com",
                "username": "user2",
                "user_source_id": user_source1.id,
            },
        ],
        str(user_source2.id): [],
    }

    with stub_user_source_registry(list_users_return=list_users_return):
        response = api_client.get(
            url,
            {"search": "second"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "users_per_user_sources" in response_json
    assert response_json["users_per_user_sources"] == {
        str(user_source1.id): [],
        str(user_source2.id): [
            {
                "id": 3,
                "role": "",
                "email": "test3@mail.com",
                "username": "user3",
                "user_source_id": user_source2.id,
            }
        ],
    }


@pytest.mark.django_db
def test_get_user_source_users_missing_application(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(workspace=workspace)
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=application
    )

    url = reverse(
        "api:user_sources:list_user_source_users",
        kwargs={"application_id": 0},
    )
    with stub_user_source_registry():
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_404_NOT_FOUND
