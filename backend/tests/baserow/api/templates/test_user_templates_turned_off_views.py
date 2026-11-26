from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from baserow.api.templates.urls import urlpatterns
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.jobs.models import Job
from baserow.core.models import Template, TemplateCategory
from tests.baserow.core.user_templates.utils import (
    ICON,
    create_template,
    install_marks,
    queued,
    run_job,
    store_template_archive,
    turn_user_templates,
)

REFUSED = (HTTP_400_BAD_REQUEST, "ERROR_USER_TEMPLATES_DISABLED")
NOT_FOUND = (HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST")


def install_url(name, workspace, template):
    return reverse(
        f"api:templates:{name}",
        kwargs={"workspace_id": workspace.id, "template_id": template.id},
    )


def slug_url(name, template):
    return reverse(f"api:templates:{name}", kwargs={"slug": template.slug})


def create_job_body(ctx):
    return {
        "type": "create_user_template",
        "workspace_id": ctx["workspace"].id,
        "application_ids": [ctx["database"].id],
        "name": "New",
        "description": "",
        "icon": ICON,
        "category_ids": [TemplateCategory.objects.create(name="Cat").id],
    }


def post_job(body):
    return lambda client, ctx: client.post(
        reverse("api:jobs:list"), body(ctx), format="json"
    )


def patch_item(body):
    return lambda client, ctx: client.patch(
        slug_url("item", ctx["template"]), body, format="json"
    )


def download(client, ctx):
    return client.post(
        slug_url("download", ctx["template"]),
        {"revision_id": ctx["template"].id},
        format="json",
    )


ROWS = [
    (
        "install",
        "official templates only",
        lambda client, ctx: client.post(
            install_url("install", ctx["workspace"], ctx["template"])
        ),
        NOT_FOUND,
    ),
    (
        "install_async",
        "install",
        lambda client, ctx: client.post(
            install_url("install_async", ctx["workspace"], ctx["template"])
        ),
        REFUSED,
    ),
    (
        "download",
        "download building the archive",
        download,
        (HTTP_202_ACCEPTED, None),
    ),
    ("download", "download of a built archive", download, (HTTP_200_OK, None)),
    (
        "rotate_private_link_token",
        "rotate the private link",
        lambda client, ctx: client.post(
            slug_url("rotate_private_link_token", ctx["template"])
        ),
        REFUSED,
    ),
    (
        "item",
        "open",
        lambda client, ctx: client.get(slug_url("item", ctx["template"])),
        NOT_FOUND,
    ),
    (
        "item",
        "make public with consent",
        patch_item({"visibility": "public", "public_listing_consent": True}),
        REFUSED,
    ),
    ("item", "turn the private link on", patch_item({"private_link": True}), REFUSED),
    (
        "item",
        "delete",
        lambda client, ctx: client.delete(slug_url("item", ctx["template"])),
        (HTTP_204_NO_CONTENT, None),
    ),
    (
        "list",
        "own list",
        lambda client, ctx: client.get(
            reverse("api:templates:list"),
            {"view": "flat", "type": "user", "owned": "true"},
        ),
        (HTTP_200_OK, None),
    ),
    (
        "list",
        "shared list",
        lambda client, ctx: client.get(
            reverse("api:templates:list"),
            {"view": "flat", "type": "user", "listed": "true"},
        ),
        (HTTP_200_OK, None),
    ),
    (
        "list",
        "public categories",
        lambda client, ctx: client.get(
            reverse("api:templates:list"), {"view": "public_categories"}
        ),
        (HTTP_200_OK, None),
    ),
    ("jobs", "create", post_job(create_job_body), REFUSED),
    (
        "jobs",
        "update the content",
        post_job(
            lambda ctx: {
                "type": "create_user_template",
                "template_id": ctx["template"].id,
                "workspace_id": ctx["workspace"].id,
                "application_ids": [ctx["database"].id],
            }
        ),
        REFUSED,
    ),
    (
        "jobs",
        "download",
        post_job(
            lambda ctx: {
                "type": "download_user_template",
                "slug": ctx["template"].slug,
                "revision_id": ctx["template"].id,
            }
        ),
        (HTTP_200_OK, None),
    ),
    (
        "jobs",
        "install",
        post_job(
            lambda ctx: {
                "type": "install_template",
                "workspace_id": ctx["workspace"].id,
                "template_id": ctx["template"].id,
            }
        ),
        REFUSED,
    ),
]


@pytest.mark.django_db
def test_every_user_template_address_refuses_while_off(api_client, data_fixture):
    assert {pattern.name for pattern in urlpatterns} <= {row[0] for row in ROWS}

    for _, label, call, (status, error) in ROWS:
        author, token = data_fixture.create_user_and_token()
        template = create_template(data_fixture, author, "public")
        workspace = data_fixture.create_workspace(user=author)
        ctx = {
            "template": template,
            "workspace": workspace,
            "database": data_fixture.create_database_application(workspace=workspace),
        }
        if label == "download of a built archive":
            store_template_archive(template)
        turn_user_templates(data_fixture, False)
        before = Template.objects.values().get(id=template.id)
        api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")

        response = call(api_client, ctx)

        assert response.status_code == status, (label, response.content)
        if error is not None:
            assert response.json()["error"] == error, label
            assert Template.objects.values().get(id=template.id) == before, label
            assert not Job.objects.filter(user=author).exists(), label
        if label == "delete":
            assert Template.objects.get(id=template.id).marked_for_deletion_at
        if label == "own list":
            assert [row["id"] for row in response.json()["results"]] == [template.id]
        if label == "shared list":
            assert response.json()["results"] == [], label
        if label == "public categories":
            assert response.json() == [], label


@install_marks
def test_instance_admin_installs_and_downloads_but_cannot_share_while_off(
    api_client, data_fixture
):
    template = create_template(data_fixture, data_fixture.create_user())
    admin, token = data_fixture.create_user_and_token(is_staff=True)
    own = create_template(data_fixture, admin, "public")
    workspace = data_fixture.create_workspace(user=admin)
    turn_user_templates(data_fixture, False)
    api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")

    with queued():
        install = api_client.post(install_url("install_async", workspace, template))
        build = api_client.post(
            slug_url("download", template), {"revision_id": template.id}, format="json"
        )

    assert install.status_code == HTTP_202_ACCEPTED, install.json()
    assert build.status_code == HTTP_202_ACCEPTED, build.json()
    for response in [install, build]:
        job = run_job(Job.objects.get(id=response.json()["id"]).specific)
        assert job.state == JOB_FINISHED, job.human_readable_error
    assert workspace.application_set.count() == 1

    archive = api_client.post(
        slug_url("download", template), {"revision_id": template.id}, format="json"
    )

    assert archive.status_code == HTTP_200_OK, archive.json()
    assert archive.json()["url"]

    rotate = api_client.post(slug_url("rotate_private_link_token", own))

    assert (rotate.status_code, rotate.json()["error"]) == REFUSED


@install_marks
def test_only_the_author_downloads_a_user_template_while_off(api_client, data_fixture):
    author, token = data_fixture.create_user_and_token()
    _, other_token = data_fixture.create_user_and_token()
    template = create_template(data_fixture, author, "public")
    turn_user_templates(data_fixture, False)

    def download_as(jwt):
        api_client.credentials(HTTP_AUTHORIZATION=f"JWT {jwt}")
        return api_client.post(
            slug_url("download", template), {"revision_id": template.id}, format="json"
        )

    refused = download_as(other_token)

    assert (refused.status_code, refused.json()["error"]) == REFUSED

    with queued():
        build = download_as(token)
    job = run_job(Job.objects.get(id=build.json()["id"]).specific)

    assert job.state == JOB_FINISHED, job.human_readable_error

    archive = download_as(token)

    assert archive.status_code == HTTP_200_OK, archive.json()
    assert archive.json()["url"]
