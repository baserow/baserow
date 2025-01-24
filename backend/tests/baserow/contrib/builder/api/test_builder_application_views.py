from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.api.user_files.serializers import UserFileSerializer
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.registries import theme_config_block_registry


@pytest.mark.django_db
def test_list_builder_applications_theme_config_block_created_number_of_queries(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_builder_application(workspace=workspace, order=1)
    data_fixture.create_builder_application(workspace=workspace, order=2)

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})

    with CaptureQueriesContext(connection) as queries_request_1:
        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    with CaptureQueriesContext(connection) as queries_request_2:
        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    # The first request executed more queries because the `MainThemeConfigBlockType`
    # entries had to be automatically created.
    assert len(queries_request_2.captured_queries) < len(
        queries_request_1.captured_queries
    )


@pytest.mark.django_db
def test_list_builder_applications_equal_number_of_queries_n_builders(
    api_client, data_fixture, bypass_check_permissions
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})

    # Making first call to make sure that the settings object is created so we can
    # accurately measure the queries later on.
    api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    data_fixture.create_builder_application(workspace=workspace, order=1)
    data_fixture.create_builder_application(workspace=workspace, order=2)

    # Force the `ThemeConfigBlockType` to be created.
    for theme_config_block_type in theme_config_block_registry.get_all():
        related_name = theme_config_block_type.related_name_in_builder_model
        [
            getattr(builder, related_name) for builder in Builder.objects.all()
        ]  # noqa: W0106

    with CaptureQueriesContext(connection) as queries_request_1:
        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    # Force the `ThemeConfigBlockType` to be created.
    for theme_config_block_type in theme_config_block_registry.get_all():
        related_name = theme_config_block_type.related_name_in_builder_model
        [
            getattr(builder, related_name) for builder in Builder.objects.all()
        ]  # noqa: W0106

    with CaptureQueriesContext(connection) as queries_request_2:
        response = api_client.get(
            url,
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    # The number of queries should not increase because another builder application
    # is added, with its own theme.
    assert len(queries_request_1.captured_queries) == len(
        queries_request_2.captured_queries
    )


@pytest.mark.django_db
def test_list_builder_applications_theme(
    api_client, data_fixture, django_assert_num_queries
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    application_1 = data_fixture.create_builder_application(
        workspace=workspace, order=1
    )
    data_fixture.create_builder_application(workspace=workspace, order=2)

    application_1.colorthemeconfigblock.primary_color = "#ccccccff"
    application_1.colorthemeconfigblock.save()

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json[0]["theme"]["primary_color"] == "#ccccccff"
    assert response_json[0]["theme"]["secondary_color"] == "#0eaa42ff"
    assert response_json[1]["theme"]["primary_color"] == "#5190efff"


@pytest.mark.django_db
def test_get_builder_application(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    favicon_file = data_fixture.create_user_file(original_extension=".png")
    application = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
        favicon_file=favicon_file,
    )

    url = reverse("api:applications:item", kwargs={"application_id": application.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    # Check we have the theme but don't want to check every single property
    assert response_json["theme"]["body_text_color"] == "#070810ff"
    del response_json["theme"]

    assert response_json == {
        "favicon_file": UserFileSerializer(application.favicon_file).data,
        "id": application.id,
        "name": application.name,
        "order": application.order,
        "created_on": application.created_on.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "type": "builder",
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "generative_ai_models_enabled": {},
        },
        "login_page_id": None,
        "pages": [
            {
                "id": application.shared_page.id,
                "builder_id": application.id,
                "order": 1,
                "name": "__shared__",
                "path": "__shared__",
                "path_params": [],
                "shared": True,
                "visibility": Page.VISIBILITY_TYPES.ALL.value,
                "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
                "roles": [],
            },
        ],
    }


@pytest.mark.django_db
def test_list_builder_applications(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    favicon_file = data_fixture.create_user_file(original_extension=".png")
    application = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
        favicon_file=favicon_file,
    )

    url = reverse("api:applications:list", kwargs={"workspace_id": workspace.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    # Check we have the theme but don't want to check every single property
    assert response_json[0]["theme"]["body_text_color"] == "#070810ff"
    del response_json[0]["theme"]

    assert response_json == [
        {
            "favicon_file": UserFileSerializer(application.favicon_file).data,
            "created_on": application.created_on.isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
            "id": application.id,
            "name": application.name,
            "order": application.order,
            "type": "builder",
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "generative_ai_models_enabled": {},
            },
            "login_page_id": None,
            "pages": [
                {
                    "id": application.shared_page.id,
                    "builder_id": application.id,
                    "order": 1,
                    "name": "__shared__",
                    "path": "__shared__",
                    "path_params": [],
                    "shared": True,
                    "visibility": Page.VISIBILITY_TYPES.ALL.value,
                    "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
                    "roles": [],
                },
            ],
        }
    ]
