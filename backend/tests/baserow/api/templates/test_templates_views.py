import os
from unittest.mock import patch

from django.conf import settings
from django.db import connection
from django.shortcuts import reverse
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow.core.job_types import InstallTemplateJobType
from baserow.core.jobs.handler import JobHandler
from baserow.core.models import Application, InstallTemplateJob, Template

TEST_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "../../../tests/templates")


@pytest.mark.django_db
def test_list_templates(api_client, data_fixture):
    category_1 = data_fixture.create_template_category(name="Cat 1")
    category_3 = data_fixture.create_template_category(name="Cat 3")
    category_2 = data_fixture.create_template_category(name="Cat 2")

    template_1 = data_fixture.create_template(
        name="Template 1",
        description="Plan projects.",
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
                    "type": "official",
                    "name": "Template 1",
                    "slug": template_1.slug,
                    "description": "Plan projects.",
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
                    "type": "official",
                    "name": "Template 2",
                    "slug": template_2.slug,
                    "description": "",
                    "icon": "document",
                    "keywords": "",
                    "workspace_id": template_2.workspace_id,
                    "is_default": False,
                    "open_application": 1,
                },
                {
                    "id": template_3.id,
                    "type": "official",
                    "name": "Template 3",
                    "slug": template_3.slug,
                    "description": "",
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
                    "type": "official",
                    "name": "Template 3",
                    "slug": template_3.slug,
                    "description": "",
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


@pytest.mark.django_db
def test_list_templates_without_user_templates(api_client, data_fixture):
    category = data_fixture.create_template_category(name="Official")
    user_category = data_fixture.create_template_category(name="User")
    official = data_fixture.create_template(category=category)
    legacy = data_fixture.create_template(type=None, category=category)
    user_template = data_fixture.create_user_template(
        categories=[category, user_category]
    )
    data_fixture.create_user_template_revision(user_template, category=category)

    response = api_client.get(reverse("api:templates:list"))
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert [c["id"] for c in response_json] == [category.id]
    assert {t["id"] for t in response_json[0]["templates"]} == {official.id, legacy.id}


@pytest.mark.django_db
def test_list_templates_keeps_category_without_templates(api_client, data_fixture):
    # A pattern sync moving a template to another category leaves the old one
    # without templates until the next full sync. Official listing is unchanged.
    empty = data_fixture.create_template_category(name="Empty")
    category = data_fixture.create_template_category(name="Official")
    data_fixture.create_template(category=category)

    response = api_client.get(reverse("api:templates:list"))
    assert response.status_code == HTTP_200_OK
    assert [c["id"] for c in response.json()] == [empty.id, category.id]


@pytest.mark.django_db
def test_get_template_ignores_user_templates_with_flag_off(
    api_client, data_fixture, settings
):
    settings.FEATURE_FLAGS = []
    official = data_fixture.create_template(type=None)
    user_template = data_fixture.create_user_template()

    response = api_client.get(
        reverse("api:templates:item", kwargs={"slug": official.slug})
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == official.id

    response = api_client.get(
        reverse("api:templates:item", kwargs={"slug": user_template.slug})
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"


def _create_installable_user_template(data_fixture, owner, state="private"):
    """
    Creates a user template of the owner in the given state, with a database in
    the workspace of its only revision unless the state says otherwise.
    """

    user_template = data_fixture.create_user_template(user=owner)
    if state == "trashed_applications":
        data_fixture.create_database_application(
            workspace=user_template.workspace, trashed=True
        )
    elif state != "no_applications":
        data_fixture.create_database_application(workspace=user_template.workspace)

    now = timezone.now()
    changes = {
        "public": {"public_revision": user_template},
        "blocked": {"blocked_at": now},
        "public_blocked": {"public_revision": user_template, "blocked_at": now},
        "marked": {"marked_for_deletion_at": now},
        "no_workspace": {"workspace": None},
        "pruned": {"pruned_at": now},
        "public_pruned": {"public_revision": user_template, "pruned_at": now},
    }.get(state, {})
    if "public_revision" in changes:
        changes["review_state"] = Template.ReviewState.APPROVED
    Template.objects.filter(id=user_template.id).update(**changes)
    user_template.refresh_from_db()
    return user_template


@pytest.mark.django_db
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_sync_install_template_ignores_user_templates(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    staff, staff_token = data_fixture.create_user_and_token(is_staff=True)
    other, other_token = data_fixture.create_user_and_token()
    # The slug matches a template file, which the official path would install.
    user_template = data_fixture.create_user_template(
        user=owner, slug="example-template-2"
    )
    data_fixture.create_database_application(workspace=user_template.workspace)
    Template.objects.filter(id=user_template.id).update(
        public_revision=user_template, review_state=Template.ReviewState.APPROVED
    )
    revision = data_fixture.create_user_template_revision(
        user_template, workspace=user_template.workspace
    )

    for user, token in [
        (owner, owner_token),
        (staff, staff_token),
        (other, other_token),
    ]:
        workspace = data_fixture.create_workspace(user=user)
        for template in [user_template, revision]:
            response = api_client.post(
                reverse(
                    "api:templates:install",
                    kwargs={"workspace_id": workspace.id, "template_id": template.id},
                ),
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
            assert response.status_code == HTTP_404_NOT_FOUND
            assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"
        assert not Application.objects.filter(workspace=workspace).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "actor,state,expected_status,expected_error",
    [
        ("owner", "private", HTTP_202_ACCEPTED, None),
        ("owner", "public", HTTP_202_ACCEPTED, None),
        ("owner", "blocked", HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_BLOCKED"),
        ("owner", "marked", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        (
            "owner",
            "no_workspace",
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ),
        (
            "owner",
            "pruned",
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ),
        (
            "owner",
            "no_applications",
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ),
        (
            "owner",
            "trashed_applications",
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ),
        # An instance admin has no access of its own.
        ("staff", "private", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        ("staff", "blocked", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        ("staff", "public", HTTP_202_ACCEPTED, None),
        ("other", "private", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        ("other", "blocked", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        ("other", "public", HTTP_202_ACCEPTED, None),
        (
            "other",
            "public_blocked",
            HTTP_404_NOT_FOUND,
            "ERROR_TEMPLATE_DOES_NOT_EXIST",
        ),
        ("other", "marked", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        (
            "other",
            "public_pruned",
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ),
    ],
)
def test_async_install_user_template_access(
    api_client,
    data_fixture,
    actor,
    state,
    expected_status,
    expected_error,
):
    owner, owner_token = data_fixture.create_user_and_token()
    user_template = _create_installable_user_template(data_fixture, owner, state)
    if actor == "owner":
        user, token = owner, owner_token
    else:
        user, token = data_fixture.create_user_and_token(is_staff=actor == "staff")
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": user_template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == expected_status, response.json()
    jobs = InstallTemplateJob.objects.filter(workspace=workspace)
    if expected_error is None:
        job = jobs.get()
        assert job.template_id == user_template.id
        assert response.json()["template"]["id"] == user_template.id
    else:
        assert response.json()["error"] == expected_error
        assert not jobs.exists()


@pytest.mark.django_db
def test_async_install_user_template_unknown_id(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": 0},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    assert not InstallTemplateJob.objects.exists()


@pytest.mark.django_db
def test_async_install_user_template_anonymous(api_client, data_fixture):
    owner = data_fixture.create_user()
    user_template = _create_installable_user_template(data_fixture, owner, "public")
    workspace = data_fixture.create_workspace(user=owner)

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": user_template.id},
        ),
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert not InstallTemplateJob.objects.exists()


@pytest.mark.django_db
def test_async_install_user_template_checks_the_workspace_first(
    api_client, data_fixture
):
    owner, token = data_fixture.create_user_and_token()
    # Blocked, so that a template check before the workspace check would show.
    user_template = _create_installable_user_template(data_fixture, owner, "blocked")
    workspace = data_fixture.create_workspace()

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": user_template.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert not InstallTemplateJob.objects.exists()


@pytest.mark.django_db
def test_install_user_template_by_revision_id_is_404(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    staff, staff_token = data_fixture.create_user_and_token(is_staff=True)
    user_template = _create_installable_user_template(data_fixture, owner, "public")
    revision = data_fixture.create_user_template_revision(
        user_template, workspace=user_template.workspace
    )

    for user, token in [(owner, owner_token), (staff, staff_token)]:
        workspace = data_fixture.create_workspace(user=user)
        response = api_client.post(
            reverse(
                "api:templates:install_async",
                kwargs={"workspace_id": workspace.id, "template_id": revision.id},
            ),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"

    assert not InstallTemplateJob.objects.exists()


@pytest.mark.django_db
def test_generic_jobs_endpoint_install_user_template_access(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    other, other_token = data_fixture.create_user_and_token()
    user_template = _create_installable_user_template(data_fixture, owner, "private")

    other_workspace = data_fixture.create_workspace(user=other)
    response = api_client.post(
        reverse("api:jobs:list"),
        {
            "type": "install_template",
            "workspace_id": other_workspace.id,
            "template_id": user_template.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND, response.json()
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    assert not InstallTemplateJob.objects.exists()

    owner_workspace = data_fixture.create_workspace(user=owner)
    response = api_client.post(
        reverse("api:jobs:list"),
        {
            "type": "install_template",
            "workspace_id": owner_workspace.id,
            "template_id": user_template.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {owner_token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    assert InstallTemplateJob.objects.get().template_id == user_template.id


@pytest.mark.django_db
@pytest.mark.parametrize(
    "actor,latest,expected_status,expected_error,expected_pin",
    [
        ("owner", False, HTTP_202_ACCEPTED, None, "public"),
        ("owner", True, HTTP_202_ACCEPTED, None, "latest"),
        ("other", False, HTTP_202_ACCEPTED, None, "public"),
        ("other", True, HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST", None),
        (
            "owner",
            "nope",
            HTTP_400_BAD_REQUEST,
            "ERROR_QUERY_PARAMETER_VALIDATION",
            None,
        ),
    ],
)
def test_async_install_user_template_latest(
    api_client,
    data_fixture,
    actor,
    latest,
    expected_status,
    expected_error,
    expected_pin,
):
    owner, owner_token = data_fixture.create_user_and_token()
    user_template = _create_installable_user_template(data_fixture, owner, "public")
    revision = data_fixture.create_user_template_revision(
        user_template, workspace=user_template.workspace
    )
    if actor == "owner":
        user, token = owner, owner_token
    else:
        user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse(
            "api:templates:install_async",
            kwargs={"workspace_id": workspace.id, "template_id": user_template.id},
        )
        + f"?latest={latest}",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == expected_status, response.json()
    jobs = InstallTemplateJob.objects.filter(workspace=workspace)
    if expected_error is None:
        pin = revision if expected_pin == "latest" else user_template
        assert jobs.get().template_id == pin.id
    else:
        assert response.json()["error"] == expected_error
        assert not jobs.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "actor,latest", [("owner", False), ("owner", True), ("other", False)]
)
def test_async_install_user_template_query_count_is_constant(
    api_client, data_fixture, actor, latest
):
    owner, owner_token = data_fixture.create_user_and_token()
    user_template = _create_installable_user_template(data_fixture, owner, "public")
    if actor == "owner":
        user, token = owner, owner_token
    else:
        user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    url = reverse(
        "api:templates:install_async",
        kwargs={"workspace_id": workspace.id, "template_id": user_template.id},
    ) + ("?latest=true" if latest else "")

    def install():
        # Only one install job of a user can run at a time.
        InstallTemplateJob.objects.all().delete()
        with CaptureQueriesContext(connection) as queries:
            response = api_client.post(url, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == HTTP_202_ACCEPTED, response.json()
        return response.json(), queries

    # The first request fills the caches that the others find filled.
    install()
    response_json, one_revision = install()
    assert response_json["template"]["id"] == user_template.id

    revisions = [
        data_fixture.create_user_template_revision(
            user_template,
            workspace=user_template.workspace,
            review_state=Template.ReviewState.APPROVED,
        )
        for _ in range(3)
    ]
    # The owner pins the latest revision when asked to, otherwise everyone pins
    # the public one.
    Template.objects.filter(id=user_template.id).update(public_revision=revisions[1])
    expected_pin = revisions[-1] if latest else revisions[1]

    response_json, four_revisions = install()
    assert InstallTemplateJob.objects.get().template_id == expected_pin.id
    assert response_json["template"]["id"] == user_template.id
    assert response_json["template"]["slug"] == user_template.slug

    assert len(four_revisions.captured_queries) == len(one_revision.captured_queries)
