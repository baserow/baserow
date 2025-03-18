import os
from unittest.mock import patch

from django.conf import settings
from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Application, Template

TEST_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "../../../tests/templates")


@pytest.mark.django_db
def test_list_templates(api_client, data_fixture):
    category_1 = data_fixture.create_template_category(name="Cat 1")
    category_3 = data_fixture.create_template_category(name="Cat 3")
    category_2 = data_fixture.create_template_category(name="Cat 2")

    template_1 = data_fixture.create_template(
        name="Template 1",
        icon="document",
        category=category_1,
        keywords="test1,test2",
        slug="project-tracker",
        open_application=None,
    )
    template_2 = data_fixture.create_template(
        name="Template 2",
        icon="document",
        category=category_2,
        open_application=1,
    )
    template_3 = data_fixture.create_template(
        name="Template 3", icon="document", categories=[category_2, category_3]
    )

    response = api_client.get(reverse("api:templates:list"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json == [
        {
            "id": category_1.id,
            "name": "Cat 1",
            "templates": [
                {
                    "id": template_1.id,
                    "name": "Template 1",
                    "slug": template_1.slug,
                    "icon": "document",
                    "keywords": "test1,test2",
                    "workspace_id": template_1.workspace_id,
                    "is_default": True,
                    "open_application": None,
                }
            ],
        },
        {
            "id": category_2.id,
            "name": "Cat 2",
            "templates": [
                {
                    "id": template_2.id,
                    "name": "Template 2",
                    "slug": template_2.slug,
                    "icon": "document",
                    "keywords": "",
                    "workspace_id": template_2.workspace_id,
                    "is_default": False,
                    "open_application": 1,
                },
                {
                    "id": template_3.id,
                    "name": "Template 3",
                    "slug": template_3.slug,
                    "icon": "document",
                    "keywords": "",
                    "workspace_id": template_3.workspace_id,
                    "is_default": False,
                    "open_application": None,
                },
            ],
        },
        {
            "id": category_3.id,
            "name": "Cat 3",
            "templates": [
                {
                    "id": template_3.id,
                    "name": "Template 3",
                    "slug": template_3.slug,
                    "icon": "document",
                    "keywords": "",
                    "workspace_id": template_3.workspace_id,
                    "is_default": False,
                    "open_application": None,
                }
            ],
        },
    ]


@pytest.mark.django_db
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_install_template(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    handler = CoreHandler()
    handler.sync_templates()

    template_2 = data_fixture.create_template(slug="does-not-exist")
    template = Template.objects.get(slug="example-template")

    response = api_client.post(
        reverse(
            "api:templates:install",
            kwargs={"workspace_id": workspace.id, "template_id": template_2.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:templates:install",
            kwargs={"workspace_id": workspace_2.id, "template_id": template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse(
            "api:templates:install",
            kwargs={"workspace_id": 0, "template_id": template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:templates:install",
            kwargs={"workspace_id": workspace.id, "template_id": 0},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:templates:install",
            kwargs={"workspace_id": workspace.id, "template_id": template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert len(response_json) == 1
    assert response_json[0]["workspace"]["id"] == workspace.id
    application = Application.objects.all().order_by("id").last()
    assert response_json[0]["id"] == application.id
    assert response_json[0]["workspace"]["id"] == application.workspace_id


@pytest.mark.django_db
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_async_install_template_errors(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    handler = CoreHandler()
    handler.sync_templates()

    template_2 = data_fixture.create_template(slug="does-not-exist")
    template = Template.objects.get(slug="example-template")

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": template_2.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TEMPLATE_FILE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace_2.id, "template_id": template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": 0, "template_id": template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": 0},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"


@pytest.mark.django_db(transaction=True)
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
@patch("baserow.core.jobs.handler.run_async_job")
def test_async_install_template_schedule_job(
    mock_run_async_job, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    handler = CoreHandler()
    handler.sync_templates()

    template = Template.objects.get(slug="example-template")

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_202_ACCEPTED
    response_json = response.json()
    assert response_json["id"] is not None
    assert response_json["state"] == "pending"
    assert response_json["type"] == "install_template"

    job = JobHandler.get_job(user, response_json["id"])
    assert job.user_id == user.id
    assert job.progress_percentage == 0
    assert job.state == "pending"
    assert job.error == ""

    mock_run_async_job.delay.assert_called_once()
    args = mock_run_async_job.delay.call_args
    assert args[0][0] == job.id


@pytest.mark.django_db(transaction=True)
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_async_install_template_serializer(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test_1@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)

    handler = CoreHandler()
    handler.sync_templates()

    template = Template.objects.get(slug="example-template")

    job = JobHandler().create_and_start_job(
        user,
        InstallTemplateJobType.type,
        workspace_id=workspace.id,
        template_id=template.id,
    )

    # check that now the job ended correctly and the application was duplicated
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    job_rsp = response.json()
    assert job_rsp["state"] == "finished"
    assert job_rsp["type"] == "install_template"
    assert job_rsp["workspace"]["id"] == workspace.id
    assert job_rsp["template"]["id"] == template.id
    assert job_rsp["template"]["name"] == template.name
    assert len(job_rsp["installed_applications"]) == 1
    installed_app = job_rsp["installed_applications"][0]
    assert installed_app["name"] == "Event marketing"
    assert installed_app["order"] == 1
    assert installed_app["workspace"]["id"] == workspace.id
    assert installed_app["type"] == "database"
