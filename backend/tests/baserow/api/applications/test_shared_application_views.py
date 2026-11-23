from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.api.applications.serializers import (
    BaseApplicationCreatePolymorphicSerializer,
    get_user_managed_application_types,
)
from baserow.core.application_types import SharedApplicationType
from baserow.core.models import Application, DuplicateApplicationJob


@pytest.mark.django_db
def test_list_applications_includes_the_shared_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)

    for url in [
        reverse("api:applications:list"),
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
    ]:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

        assert response.status_code == HTTP_200_OK
        assert [(app["id"], app["type"]) for app in response.json()] == [
            (shared_application.id, SharedApplicationType.type)
        ]


@pytest.mark.django_db
def test_create_shared_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Shared", "type": SharedApplicationType.type},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # Refused as an invalid type, like the API documentation says.
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["type"][0]["code"] == "invalid_choice"
    assert not Application.objects.filter(workspace=workspace).exists()


def test_the_shared_type_cannot_be_chosen_when_creating_an_application():
    choices = BaseApplicationCreatePolymorphicSerializer().fields["type"].choices

    assert SharedApplicationType.type not in choices
    assert "database" in choices


@pytest.mark.django_db
def test_the_api_documentation_offers_no_shared_application_to_create_or_update(
    api_client,
):
    schema = api_client.get(reverse("api:json_schema")).json()
    components = schema["components"]["schemas"]

    def request_variants(path, method):
        body = schema["paths"][path][method]["requestBody"]["content"]
        ref = body["application/json"]["schema"]["$ref"].split("/")[-1]
        return [
            sub["$ref"].split("/")[-1]
            for sub in components[ref].get("anyOf", components[ref].get("oneOf", []))
        ]

    create = request_variants("/api/applications/workspace/{workspace_id}/", "post")
    update = request_variants("/api/applications/{application_id}/", "patch")

    user_managed = len(get_user_managed_application_types())
    for variants in (create, update):
        assert len(variants) == user_managed
        assert any(name.startswith("Database") for name in variants)
        assert not any("SharedApplication" in name for name in variants)


@pytest.mark.django_db
def test_update_delete_or_duplicate_shared_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    item_url = reverse(
        "api:applications:item", kwargs={"application_id": shared_application.id}
    )
    duplicate_url = reverse(
        "api:applications:async_duplicate",
        kwargs={"application_id": shared_application.id},
    )

    responses = [
        api_client.patch(
            item_url,
            {"name": "Renamed"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        ),
        api_client.delete(item_url, HTTP_AUTHORIZATION=f"JWT {token}"),
        api_client.post(duplicate_url, HTTP_AUTHORIZATION=f"JWT {token}"),
    ]

    for response in responses:
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_APPLICATION_OPERATION_NOT_SUPPORTED"
    shared_application.refresh_from_db()
    assert shared_application.name == "__shared__"
    assert not shared_application.trashed
    assert not DuplicateApplicationJob.objects.exists()
