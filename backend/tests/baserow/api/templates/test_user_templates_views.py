from datetime import datetime, timezone

from django.db import connection
from django.db.models import F
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext
from django.utils import timezone as django_timezone

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.models import Template, TemplateCategory
from baserow.core.user_templates.job_types import CreateUserTemplateJobType
from baserow.core.user_templates.models import CreateUserTemplateJob

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api:templates:list")


def create_own_template(data_fixture, user, **kwargs):
    kwargs.setdefault("icon", "iconoir-view-grid")
    return data_fixture.create_user_template(user=user, **kwargs)


def publish(template):
    Template.objects.filter(id=template.id).update(public_revision_id=F("id"))
    template.refresh_from_db()
    return template


def list_templates(api_client, token=None, **params):
    params.setdefault("view", "flat")
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.get(LIST_URL, params, **headers)


def list_own_templates(api_client, token, **params):
    return list_templates(api_client, token, type="user", owned="true", **params)


def test_list_own_templates(api_client, data_fixture):
    # Which templates are listed and in which order is tested on the handler.
    user, token = data_fixture.create_user_and_token()
    category_1 = data_fixture.create_template_category(name="Cat 1")
    category_2 = data_fixture.create_template_category(name="Cat 2")
    with freeze_time("2026-10-01 10:00"):
        template = create_own_template(
            data_fixture,
            user,
            name="Older",
            categories=[category_1],
        )
    # The latest revision is shown, with the id, slug and dates of the template.
    source_workspace = data_fixture.create_workspace(user=user)
    with freeze_time("2026-10-02 10:00"):
        latest = data_fixture.create_user_template_revision(
            template,
            name="Older v2",
            description="Plans projects.",
            icon="iconoir-coins",
            categories=[category_2, category_1],
            open_application=1,
            review_state="rejected",
            reject_reason="Not a template.",
            metadata={
                "source_workspace_id": source_workspace.id,
                "source_application_ids": [3, 1],
            },
        )

    response = list_own_templates(api_client, token)

    assert response.status_code == HTTP_200_OK
    assert response.json()["results"] == [
        {
            "id": template.id,
            "type": "user",
            "name": "Older v2",
            "slug": template.slug,
            "description": "Plans projects.",
            "icon": "iconoir-coins",
            "keywords": "",
            "workspace_id": latest.workspace_id,
            "is_default": False,
            "open_application": 1,
            "categories": [
                {"id": category_1.id, "name": "Cat 1"},
                {"id": category_2.id, "name": "Cat 2"},
            ],
            "state": "rejected",
            "reason": "Not a template.",
            "source_workspace_id": source_workspace.id,
            "source_application_ids": [3, 1],
            "install_count": 0,
            "created_on": "2026-10-01T10:00:00Z",
            "updated_on": "2026-10-01T10:00:00Z",
        }
    ]


def test_list_own_templates_shows_state_of_the_latest_revision(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    template = create_own_template(
        data_fixture,
        user,
        review_state="rejected",
        reject_reason="Not a template.",
        blocked_reason="Spam",
    )
    data_fixture.create_user_template_revision(template)

    response = list_own_templates(api_client, token)

    assert response.status_code == HTTP_200_OK
    result = response.json()["results"][0]
    assert (result["state"], result["reason"]) == ("private", None)

    template.blocked_at = django_timezone.now()
    template.save()

    response = list_own_templates(api_client, token)

    assert response.status_code == HTTP_200_OK
    result = response.json()["results"][0]
    assert (result["state"], result["reason"]) == ("blocked", "Spam")


def test_list_templates_lists_what_the_actor_can_open(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    _, stranger_token = data_fixture.create_user_and_token()
    official = data_fixture.create_template()
    public = publish(create_own_template(data_fixture, owner))
    private = create_own_template(data_fixture, owner)
    blocked = publish(
        create_own_template(data_fixture, owner, blocked_at=django_timezone.now())
    )

    def listed_ids(token):
        response = list_templates(api_client, token)
        assert response.status_code == HTTP_200_OK
        return {t["id"] for t in response.json()["results"]}

    assert listed_ids(None) == {official.id, public.id}
    assert listed_ids(stranger_token) == {official.id, public.id}
    assert listed_ids(owner_token) == {official.id, public.id, private.id, blocked.id}


def test_list_templates_shows_others_the_public_revision(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    _, stranger_token = data_fixture.create_user_and_token()
    template = publish(create_own_template(data_fixture, owner, name="Public"))
    data_fixture.create_user_template_revision(template, name="Latest")

    def listed_names(token):
        response = list_templates(api_client, token, type="user")
        assert response.status_code == HTTP_200_OK
        return [t["name"] for t in response.json()["results"]]

    assert listed_names(None) == ["Public"]
    assert listed_names(stranger_token) == ["Public"]
    assert listed_names(owner_token) == ["Latest"]


def test_list_templates_hides_the_state_from_others(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    _, stranger_token = data_fixture.create_user_and_token()
    # Staff who don't own the template are others too.
    _, staff_token = data_fixture.create_user_and_token(is_staff=True)
    template = publish(
        create_own_template(data_fixture, owner, metadata={"source_workspace_id": 1})
    )
    data_fixture.create_user_template_revision(
        template, metadata={"source_workspace_id": 1}
    )
    Template.objects.filter(id=template.id).update(install_count=3)
    data_fixture.create_template(install_count=5)
    owner_only = (
        "state",
        "reason",
        "source_workspace_id",
        "source_application_ids",
        "install_count",
    )

    for token in [None, stranger_token, staff_token]:
        response = list_templates(api_client, token)
        assert response.status_code == HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 2
        assert {tuple(t[key] for key in owner_only) for t in results} == {
            (None, None, None, None, None)
        }

    response = list_templates(api_client, owner_token, type="user")
    result = response.json()["results"][0]
    assert result["id"] == template.id
    # The count is the root's, while the latest revision is listed.
    assert (result["state"], result["source_workspace_id"]) == ("public", 1)
    assert result["install_count"] == 3


def test_list_templates_filters_by_type(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    official = data_fixture.create_template()
    # Templates created before the type existed are official.
    legacy = data_fixture.create_template(type=None)
    own = create_own_template(data_fixture, user)

    response = list_templates(api_client, token, type="official")
    assert {t["id"] for t in response.json()["results"]} == {official.id, legacy.id}
    assert {t["type"] for t in response.json()["results"]} == {"official"}

    response = list_templates(api_client, token, type="user")
    assert [t["id"] for t in response.json()["results"]] == [own.id]


def test_list_templates_filters_by_owner(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    data_fixture.create_template()
    publish(data_fixture.create_user_template())
    own = create_own_template(data_fixture, user)

    response = list_templates(api_client, token, owned="true")
    assert [t["id"] for t in response.json()["results"]] == [own.id]

    response = list_templates(api_client, owned="true")
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 0


def test_list_own_templates_paging(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    templates = [
        create_own_template(data_fixture, user, name=f"Template {index}")
        for index in range(25)
    ]
    expected_ids = [template.id for template in reversed(templates)]

    response = list_own_templates(api_client, token)
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 25
    assert [t["id"] for t in response_json["results"]] == expected_ids[:20]
    assert response_json["next"] is not None

    response = list_own_templates(api_client, token, limit=20, offset=20)
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert [t["id"] for t in response_json["results"]] == expected_ids[20:]
    assert response_json["next"] is None


def test_list_own_templates_limit_is_capped(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    category = data_fixture.create_template_category()
    for _ in range(101):
        create_own_template(data_fixture, user, category=category)

    response = list_own_templates(api_client, token, limit=1000)

    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 101
    assert len(response.json()["results"]) == 100


def test_list_own_templates_search(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    by_name = create_own_template(data_fixture, user, name="CRM", description="")
    by_description = create_own_template(
        data_fixture, user, name="Sales", description="A small crm for a shop."
    )
    create_own_template(data_fixture, user, name="Tasks", description="To do.")
    publish(data_fixture.create_user_template(name="CRM of another user"))
    # Only the latest revision is searched.
    by_latest = create_own_template(data_fixture, user, name="Notes")
    data_fixture.create_user_template_revision(by_latest, name="CRM notes")
    renamed = create_own_template(data_fixture, user, name="Old CRM")
    data_fixture.create_user_template_revision(renamed, name="Contacts")

    response = list_own_templates(api_client, token, search="crm")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 3
    assert {t["id"] for t in response_json["results"]} == {
        by_name.id,
        by_description.id,
        by_latest.id,
    }

    response = list_own_templates(api_client, token, search="")

    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 5


def test_list_own_templates_query_count_is_constant(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    categories = [data_fixture.create_template_category() for _ in range(2)]

    def create_template_with_revisions(install_count):
        template = create_own_template(data_fixture, user, categories=list(categories))
        for _ in range(2):
            data_fixture.create_user_template_revision(
                template, categories=list(categories)
            )
        Template.objects.filter(id=template.id).update(install_count=install_count)
        return template

    first = create_template_with_revisions(1)

    with CaptureQueriesContext(connection) as one_template:
        response = list_own_templates(api_client, token)
        assert response.status_code == HTTP_200_OK
        assert response.json()["results"][0]["install_count"] == 1

    others = [create_template_with_revisions(n) for n in (0, 2, 7)]

    with CaptureQueriesContext(connection) as four_templates:
        response = list_own_templates(api_client, token)
        assert response.status_code == HTTP_200_OK
        assert response.json()["count"] == 4
        assert {t["id"]: t["install_count"] for t in response.json()["results"]} == {
            first.id: 1,
            others[0].id: 0,
            others[1].id: 2,
            others[2].id: 7,
        }

    assert len(four_templates.captured_queries) == len(one_template.captured_queries)


def test_list_templates_with_flag_off(api_client, data_fixture, settings):
    settings.FEATURE_FLAGS = []
    user, token = data_fixture.create_user_and_token()
    official = data_fixture.create_template()
    create_own_template(data_fixture, user)

    response = list_templates(api_client, token)

    assert response.status_code == HTTP_200_OK
    assert [t["id"] for t in response.json()["results"]] == [official.id]


def test_list_templates_with_an_invalid_parameter(api_client, data_fixture):
    response = list_templates(api_client, type="other")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


def test_list_template_categories_ignores_the_parameters(api_client, data_fixture):
    # The deprecated categories never read the parameters, so old clients sending
    # any keep working.
    category = data_fixture.create_template_category(name="Official")
    data_fixture.create_template(category=category)

    response = list_templates(api_client, view="tree", type="other", search="")

    assert response.status_code == HTTP_200_OK
    assert [c["id"] for c in response.json()] == [category.id]


@pytest.mark.django_db
def test_get_user_template_shows_its_public_revision(api_client, data_fixture):
    owner, token = data_fixture.create_user_and_token()
    template = create_own_template(data_fixture, owner, name="First", keywords="crm")
    public = data_fixture.create_user_template_revision(template, name="Second")
    Template.objects.filter(id=template.id).update(public_revision=public)
    latest = data_fixture.create_user_template_revision(
        template,
        name="Third",
        description="Latest",
        icon="iconoir-coins",
        open_application=7,
    )
    url = reverse("api:templates:item", kwargs={"slug": template.slug})

    def get_shown(headers):
        response = api_client.get(url, **headers)
        assert response.status_code == HTTP_200_OK
        result = response.json()
        return result["id"], result["name"], result["workspace_id"]

    # Everyone sees the public revision, the owner too.
    for headers in [{}, {"HTTP_AUTHORIZATION": f"JWT {token}"}]:
        assert get_shown(headers) == (template.id, "Second", public.workspace_id)

    # The owner sees the latest revision while the template isn't public, or is
    # blocked.
    for changes in [{"public_revision": None}, {"blocked_at": django_timezone.now()}]:
        Template.objects.filter(id=template.id).update(
            public_revision=public, blocked_at=None
        )
        Template.objects.filter(id=template.id).update(**changes)
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {token}")

        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "id": template.id,
            "type": "user",
            "name": "Third",
            "slug": template.slug,
            "description": "Latest",
            "icon": "iconoir-coins",
            "keywords": "crm",
            "workspace_id": latest.workspace_id,
            "is_default": False,
            "open_application": 7,
        }


def create_job(api_client, token, workspace, applications, **overrides):
    category = TemplateCategory.objects.create(name="Cat")
    data = {
        "type": CreateUserTemplateJobType.type,
        "workspace_id": workspace.id,
        "application_ids": [application.id for application in applications],
        "name": "My template",
        "description": "What it does",
        "icon": "iconoir-view-grid",
        "category_ids": [category.id],
        **overrides,
    }
    data = {key: value for key, value in data.items() if value is not None}
    return api_client.post(
        reverse("api:jobs:list"),
        data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"workspace_id": None}, "workspace_id"),
        ({"name": None}, "name"),
        ({"name": ""}, "name"),
        ({"name": "x" * 65}, "name"),
        ({"description": "x" * 81}, "description"),
        ({"icon": "iconoir-" + "a" * 30}, "icon"),
        ({"icon": None}, "icon"),
        ({"category_ids": None}, "category_ids"),
        ({"application_ids": []}, "application_ids"),
        ({"application_ids": None}, "application_ids"),
    ],
)
def test_create_user_template_job_request_validation(
    api_client, data_fixture, overrides, field
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    response = create_job(api_client, token, workspace, [database], **overrides)

    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert list(response_json["detail"]) == [field]
    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.parametrize("unknown", [True, False])
def test_create_user_template_job_with_invalid_categories(
    api_client, data_fixture, unknown
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    category = TemplateCategory.objects.create(name="Cat")
    category_ids = [category.id, category.id + 1000] if unknown else []

    response = create_job(
        api_client, token, workspace, [database], category_ids=category_ids
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_TEMPLATE_CATEGORY"
    assert not CreateUserTemplateJob.objects.exists()


def test_create_user_template_job_accepts_valid_request(
    api_client, data_fixture, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    response = create_job(
        api_client, token, workspace, [database], description=None, name="x" * 64
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["type"] == CreateUserTemplateJobType.type
    assert response_json["template"] is None
    assert response_json["revision"] is None
    # The request is sent back, so that the wizard can show a running job again.
    assert {
        key: response_json[key]
        for key in [
            "workspace_id",
            "application_ids",
            "name",
            "description",
            "icon",
            "category_ids",
        ]
    } == {
        "workspace_id": workspace.id,
        "application_ids": [database.id],
        "name": "x" * 64,
        "description": "",
        "icon": "iconoir-view-grid",
        "category_ids": [TemplateCategory.objects.get().id],
    }
    job = CreateUserTemplateJob.objects.get(id=response_json["id"])
    assert job.description == ""
    assert job.name == "x" * 64


@pytest.mark.django_db
def test_create_user_template_job_with_template_id_null(
    api_client, data_fixture, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    category = TemplateCategory.objects.create(name="Cat")

    response = api_client.post(
        reverse("api:jobs:list"),
        {
            "type": CreateUserTemplateJobType.type,
            "template_id": None,
            "workspace_id": workspace.id,
            "application_ids": [database.id],
            "name": "My template",
            "description": "",
            "icon": "iconoir-view-grid",
            "category_ids": [category.id],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    job = CreateUserTemplateJob.objects.get(id=response.json()["id"])
    assert job.template_id is None
    assert job.source_workspace_id == workspace.id


@pytest.mark.django_db
def test_create_user_template_job_with_flag_off(api_client, data_fixture, settings):
    settings.FEATURE_FLAGS = []
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    response = create_job(api_client, token, workspace, [database])

    assert response.status_code == HTTP_403_FORBIDDEN
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert not CreateUserTemplateJob.objects.exists()


def update_job(api_client, token, template, **data):
    return api_client.post(
        reverse("api:jobs:list"),
        {"type": CreateUserTemplateJobType.type, "template_id": template.id, **data},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_update_user_template_job_accepts_valid_requests(
    api_client, data_fixture, use_tmp_media_root
):
    user, token = data_fixture.create_user_and_token()
    template = create_own_template(data_fixture, user)
    category = TemplateCategory.objects.create(name="Cat")
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    response = update_job(
        api_client,
        token,
        template,
        name="Renamed",
        description="",
        icon="iconoir-calendar",
        category_ids=[category.id],
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["template"] == template.id
    assert response_json["revision"] is None
    assert response_json["workspace_id"] is None
    assert response_json["application_ids"] == []
    assert response_json["name"] == "Renamed"
    job = CreateUserTemplateJob.objects.get(id=response_json["id"])
    assert job.base_revision_id == template.id
    job.delete()

    response = update_job(
        api_client,
        token,
        template,
        workspace_id=workspace.id,
        application_ids=[database.id],
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["template"] == template.id
    assert response_json["workspace_id"] == workspace.id
    assert response_json["application_ids"] == [database.id]
    # The details are kept from the latest revision.
    assert response_json["name"] == template.name
    assert response_json["category_ids"] == [
        category.id for category in template.categories.all()
    ]


@pytest.mark.django_db
def test_update_user_template_job_request_modes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    template = create_own_template(data_fixture, user)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    response = update_job(
        api_client,
        token,
        template,
        workspace_id=workspace.id,
        application_ids=[database.id],
        name="Renamed",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert list(response.json()["detail"]) == ["name"]

    response = update_job(api_client, token, template, name="Renamed")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert sorted(response.json()["detail"]) == [
        "category_ids",
        "description",
        "icon",
    ]
    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.django_db
def test_update_user_template_job_of_a_template_not_owned(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    template = create_own_template(data_fixture, data_fixture.create_user())
    category = TemplateCategory.objects.create(name="Cat")

    response = update_job(
        api_client,
        token,
        template,
        name="Renamed",
        description="",
        icon="iconoir-calendar",
        category_ids=[category.id],
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.django_db
def test_update_user_template_job_cannot_reach_another_users_content(
    api_client, data_fixture
):
    owner, owner_token = data_fixture.create_user_and_token()
    user, token = data_fixture.create_user_and_token()
    category = TemplateCategory.objects.create(name="Cat")
    owner_template = create_own_template(data_fixture, owner)
    revision = data_fixture.create_user_template_revision(owner_template)
    data_fixture.create_database_application(workspace=revision.workspace)
    owner_workspace = data_fixture.create_workspace(user=owner)
    data_fixture.create_database_application(workspace=owner_workspace)
    template = create_own_template(data_fixture, user)
    details = {
        "name": "Renamed",
        "description": "",
        "icon": "iconoir-calendar",
        "category_ids": [category.id],
    }

    # Neither a revision of another user's template nor its content.
    response = update_job(api_client, token, revision, **details)
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    for workspace in [owner_workspace, revision.workspace]:
        response = update_job(
            api_client,
            token,
            template,
            workspace_id=workspace.id,
            application_ids=list(
                workspace.application_set.values_list("id", flat=True)
            ),
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert not CreateUserTemplateJob.objects.exists()

    # Nor the update job of another user.
    job_id = update_job(api_client, owner_token, owner_template, **details).json()["id"]
    response = api_client.get(
        reverse("api:jobs:item", kwargs={"job_id": job_id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    response = api_client.post(
        reverse("api:jobs:cancel", kwargs={"job_id": job_id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_user_template_content_whose_categories_are_deleted(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    template = create_own_template(data_fixture, user)
    template.categories.all().delete()
    # Another category exists, so the template needs one.
    TemplateCategory.objects.create(name="Other")
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    response = update_job(
        api_client,
        token,
        template,
        workspace_id=workspace.id,
        application_ids=[database.id],
    )

    # Refused before the content is copied.
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_TEMPLATE_CATEGORY"
    assert not CreateUserTemplateJob.objects.exists()


@pytest.mark.django_db
def test_update_user_template_details_without_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    template = create_own_template(data_fixture, user)
    Template.objects.filter(id=template.id).update(workspace=None)
    category = TemplateCategory.objects.create(name="Cat")

    response = update_job(
        api_client,
        token,
        template,
        name="Renamed",
        description="",
        icon="iconoir-calendar",
        category_ids=[category.id],
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_TEMPLATE_HAS_NO_CONTENT"
    assert not CreateUserTemplateJob.objects.exists()


def create_template_with_rows(data_fixture, template):
    database = data_fixture.create_database_application(workspace=template.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, primary=True)
    table.get_model().objects.create(**{field.db_column: "Row"})
    return data_fixture.create_grid_view(table=table)


def get_as_anonymous_stranger_and_owner(api_client, tokens, url):
    return tuple(
        api_client.get(url, **headers).status_code
        for headers in [{}]
        + [{"HTTP_AUTHORIZATION": f"JWT {token}"} for token in tokens]
    )


@pytest.mark.parametrize("user_templates_enabled", [True, False])
def test_open_user_template(api_client, data_fixture, settings, user_templates_enabled):
    if not user_templates_enabled:
        settings.FEATURE_FLAGS = []
    _, stranger_token = data_fixture.create_user_and_token()
    owner, owner_token = data_fixture.create_user_and_token()
    tokens = [stranger_token, owner_token]
    official = data_fixture.create_template()
    user_template = data_fixture.create_user_template(user=owner)
    marked = data_fixture.create_user_template(
        user=owner, marked_for_deletion_at=datetime(2026, 10, 1, tzinfo=timezone.utc)
    )

    # Anonymous, a stranger and the owner.
    for template, opens in [
        (official, (True, True, True)),
        (user_template, (False, False, user_templates_enabled)),
        (marked, (False, False, False)),
    ]:
        grid = create_template_with_rows(data_fixture, template)

        statuses = get_as_anonymous_stranger_and_owner(
            api_client,
            tokens,
            reverse("api:templates:item", kwargs={"slug": template.slug}),
        )
        assert statuses == tuple(
            HTTP_200_OK if allowed else HTTP_404_NOT_FOUND for allowed in opens
        )

        # Not a member, so a signed in user gets a 400 when it's refused.
        refused = (HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST, HTTP_400_BAD_REQUEST)
        statuses = get_as_anonymous_stranger_and_owner(
            api_client,
            tokens,
            reverse(
                "api:applications:list",
                kwargs={"workspace_id": template.workspace_id},
            ),
        )
        assert statuses == tuple(
            HTTP_200_OK if allowed else status
            for allowed, status in zip(opens, refused)
        )

        statuses = get_as_anonymous_stranger_and_owner(
            api_client,
            tokens,
            reverse("api:database:views:grid:list", kwargs={"view_id": grid.id}),
        )
        assert statuses == tuple(
            HTTP_200_OK if allowed else status
            for allowed, status in zip(opens, refused)
        )


def test_template_by_slug_has_its_type(api_client, data_fixture):
    owner, token = data_fixture.create_user_and_token()
    official = data_fixture.create_template()
    legacy = data_fixture.create_template(type=None)
    user_template = data_fixture.create_user_template(user=owner)

    for template, template_type in [
        (official, "official"),
        (legacy, "official"),
        (user_template, "user"),
    ]:
        response = api_client.get(
            reverse("api:templates:item", kwargs={"slug": template.slug}),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["type"] == template_type


def delete_template(api_client, token, slug):
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.delete(
        reverse("api:templates:item", kwargs={"slug": slug}), **headers
    )


def is_marked(template):
    return Template.objects.get(id=template.id).marked_for_deletion_at is not None


def create_template_in_state(data_fixture, owner, state):
    template = create_own_template(data_fixture, owner)
    if state == "shared":
        Template.objects.filter(id=template.id).update(shared_revision_id=F("id"))
    elif state == "public":
        revision = data_fixture.create_user_template_revision(template)
        Template.objects.filter(id=template.id).update(public_revision=revision)
    elif state == "blocked":
        Template.objects.filter(id=template.id).update(blocked_at=django_timezone.now())
    return template


@pytest.mark.parametrize("state", ["private", "shared", "public", "blocked"])
@pytest.mark.parametrize("as_staff", [False, True])
def test_delete_user_template(api_client, data_fixture, state, as_staff):
    owner, owner_token = data_fixture.create_user_and_token()
    _, staff_token = data_fixture.create_user_and_token(is_staff=True)
    template = create_template_in_state(data_fixture, owner, state)
    other = create_own_template(data_fixture, owner)

    response = delete_template(
        api_client, staff_token if as_staff else owner_token, template.slug
    )

    assert response.status_code == 204
    assert is_marked(template)
    assert not is_marked(other)


def test_delete_user_template_refused(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    _, other_token = data_fixture.create_user_and_token()
    _, staff_token = data_fixture.create_user_and_token(is_staff=True)
    template = create_own_template(data_fixture, owner)
    official = data_fixture.create_template()

    for token, slug, status in [
        (None, template.slug, HTTP_401_UNAUTHORIZED),
        (other_token, template.slug, HTTP_404_NOT_FOUND),
        (staff_token, official.slug, HTTP_404_NOT_FOUND),
        (staff_token, "unknown", HTTP_404_NOT_FOUND),
    ]:
        response = delete_template(api_client, token, slug)

        assert response.status_code == status
        if status == HTTP_404_NOT_FOUND:
            assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"

    assert not Template.objects.filter(marked_for_deletion_at__isnull=False).exists()


def test_delete_user_template_twice(api_client, data_fixture):
    owner, owner_token = data_fixture.create_user_and_token()
    _, staff_token = data_fixture.create_user_and_token(is_staff=True)
    template = create_own_template(data_fixture, owner)

    assert delete_template(api_client, owner_token, template.slug).status_code == 204
    marked_at = Template.objects.get(id=template.id).marked_for_deletion_at

    for token in [owner_token, staff_token]:
        response = delete_template(api_client, token, template.slug)

        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["error"] == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    assert Template.objects.get(id=template.id).marked_for_deletion_at == marked_at


@pytest.mark.parametrize("deleted_by", ["owner", "staff"])
def test_deleted_user_template_is_gone_for_everybody(
    api_client, data_fixture, deleted_by
):
    owner, owner_token = data_fixture.create_user_and_token()
    _, other_token = data_fixture.create_user_and_token()
    _, staff_token = data_fixture.create_user_and_token(is_staff=True)
    tokens = [owner_token, other_token, staff_token]
    template = create_own_template(data_fixture, owner)
    # Revisions have no slug: the root's slug opens the public revision for others.
    revision = data_fixture.create_user_template_revision(template)
    Template.objects.filter(id=template.id).update(public_revision=revision)
    root_grid = create_template_with_rows(data_fixture, template)
    revision_grid = create_template_with_rows(data_fixture, revision)
    url = reverse("api:templates:item", kwargs={"slug": template.slug})
    assert get_as_anonymous_stranger_and_owner(api_client, tokens, url) == (
        (HTTP_200_OK,) * 4
    )
    for token in tokens:
        results = list_templates(api_client, token).json()["results"]
        assert [t["id"] for t in results] == [template.id]

    token = owner_token if deleted_by == "owner" else staff_token
    assert delete_template(api_client, token, template.slug).status_code == 204

    url = reverse("api:templates:item", kwargs={"slug": template.slug})
    assert get_as_anonymous_stranger_and_owner(api_client, tokens, url) == (
        (HTTP_404_NOT_FOUND,) * 4
    )
    for token in tokens:
        assert list_templates(api_client, token).json()["results"] == []
    assert list_own_templates(api_client, owner_token).json()["results"] == []

    # The owner, a stranger and an instance admin aren't members of the template
    # workspaces.
    refused = (HTTP_401_UNAUTHORIZED,) + (HTTP_400_BAD_REQUEST,) * 3
    for workspace_id, grid in [
        (template.workspace_id, root_grid),
        (revision.workspace_id, revision_grid),
    ]:
        url = reverse("api:applications:list", kwargs={"workspace_id": workspace_id})
        assert get_as_anonymous_stranger_and_owner(api_client, tokens, url) == refused
        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid.id})
        assert get_as_anonymous_stranger_and_owner(api_client, tokens, url) == refused


def test_delete_user_template_query_count_is_linear_in_its_jobs(
    api_client, data_fixture
):
    owner, token = data_fixture.create_user_and_token()
    query_counts = []
    for job_count in [0, 1, 3]:
        template = create_own_template(data_fixture, owner)
        for _ in range(job_count):
            CreateUserTemplateJob.objects.create(
                user=owner,
                template=template,
                base_revision=template,
                name="Update",
                icon="iconoir-view-grid",
            )

        with CaptureQueriesContext(connection) as queries:
            assert delete_template(api_client, token, template.slug).status_code == 204
        query_counts.append(len(queries.captured_queries))

    assert CreateUserTemplateJob.objects.filter(state="cancelled").count() == 4
    # Each update job is locked and cancelled on its own, the rest is constant.
    no_job, one_job, three_jobs = query_counts
    assert three_jobs - no_job == 3 * (one_job - no_job)
