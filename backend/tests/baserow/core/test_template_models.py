from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import reverse
from django.test.utils import override_settings
from django.utils import timezone

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.table.handler import TableUsageHandler
from baserow.contrib.database.table.models import TableUsage
from baserow.core.handler import CoreHandler
from baserow.core.models import Template, Workspace
from baserow.core.usage.handler import UsageHandler


def assert_rejected(**kwargs):
    with pytest.raises(IntegrityError), transaction.atomic():
        Template.objects.filter(pk=kwargs.pop("pk")).update(**kwargs)


@pytest.mark.django_db
def test_template_querysets_split_official_and_user_templates(data_fixture):
    official = data_fixture.create_template()
    legacy = data_fixture.create_template(type=None)
    user_template = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(user_template)

    assert set(Template.objects.official()) == {official, legacy}
    assert set(Template.objects.user()) == {user_template, revision}
    assert Template.objects.count() == 4


@pytest.mark.django_db
def test_template_latest_revisions_returns_one_row_per_template(
    data_fixture, django_assert_num_queries
):
    official = data_fixture.create_template()
    root = data_fixture.create_user_template()
    data_fixture.create_user_template_revision(root)
    latest = data_fixture.create_user_template_revision(root)
    root_only = data_fixture.create_user_template()
    other_root = data_fixture.create_user_template()
    other_latest = data_fixture.create_user_template_revision(other_root)

    with django_assert_num_queries(1):
        rows = list(Template.objects.latest_revisions())
        roots = {row.id: row.get_root() for row in rows}

    assert set(rows) == {official, latest, root_only, other_latest}
    assert roots == {
        official.id: official,
        latest.id: root,
        root_only.id: root_only,
        other_latest.id: other_root,
    }
    # The latest revision among the rows in the queryset.
    assert set(
        Template.objects.filter(id__in=[root.id, root_only.id]).latest_revisions()
    ) == {root, root_only}
    assert list(Template.objects.filter(id=latest.id).latest_revisions()) == [latest]


@pytest.mark.django_db
def test_template_checks_reject_root_fields_on_a_revision(data_fixture):
    user = data_fixture.create_user()
    root = data_fixture.create_user_template(user=user)
    revision = data_fixture.create_user_template_revision(root)
    assert revision.version == 2

    for kwargs in [
        {"slug": "revision"},
        {"owner": user},
        {"author": user},
        {"public_revision": revision},
        {"shared_revision": revision},
        {"private_link_token": "a" * 64},
        {"blocked_at": timezone.now()},
        {"blocked_by": user},
        {"blocked_reason": "Spam"},
        {"marked_for_deletion_at": timezone.now()},
        {"install_count": 1},
        {"version": 1},
    ]:
        assert_rejected(pk=revision.pk, **kwargs)


@pytest.mark.django_db
def test_template_checks_reject_invalid_rows(data_fixture):
    user = data_fixture.create_user()
    official = data_fixture.create_template()
    legacy = data_fixture.create_template(type=None)
    root = data_fixture.create_user_template(user=user)
    revision = data_fixture.create_user_template_revision(root)

    assert_rejected(pk=official.pk, version=2)
    assert_rejected(pk=official.pk, slug="")
    assert_rejected(pk=official.pk, slug=root.slug)
    assert_rejected(pk=official.pk, type="")
    assert_rejected(pk=official.pk, type="unknown")
    assert_rejected(pk=official.pk, owner=user)
    assert_rejected(pk=official.pk, author=user)
    assert_rejected(pk=legacy.pk, owner=user)
    assert_rejected(pk=legacy.pk, author=user)
    assert_rejected(pk=root.pk, owner=None)
    assert_rejected(pk=root.pk, private_link_token="")
    assert_rejected(pk=revision.pk, version=0)

    with pytest.raises(IntegrityError), transaction.atomic():
        data_fixture.create_user_template_revision(root, version=2)


@pytest.mark.django_db
def test_template_checks_allow_valid_rows(data_fixture):
    root = data_fixture.create_user_template()

    Template.objects.filter(pk=root.pk).update(
        owner=None, marked_for_deletion_at=timezone.now()
    )
    Template.objects.filter(pk=root.pk).update(private_link_token="a" * 64)
    data_fixture.create_user_template_revision(root)
    data_fixture.create_user_template_revision(root)

    assert root.revisions.count() == 2


@pytest.mark.django_db
def test_template_clean_rejects_rows_breaking_the_family(data_fixture):
    root = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(root)
    other_root = data_fixture.create_user_template()
    other_revision = data_fixture.create_user_template_revision(other_root)

    root.clean()
    revision.clean()

    revision.root = other_revision
    with pytest.raises(ValidationError) as exc:
        revision.clean()
    assert "root" in exc.value.message_dict

    revision.root = root
    revision.type = Template.Type.OFFICIAL
    with pytest.raises(ValidationError) as exc:
        revision.clean()
    assert "type" in exc.value.message_dict
    revision.type = Template.Type.USER

    root.public_revision = other_revision
    root.shared_revision = other_revision
    with pytest.raises(ValidationError) as exc:
        root.clean()
    assert set(exc.value.message_dict) == {"public_revision", "shared_revision"}

    root.shared_revision = revision
    root.public_revision = revision
    with pytest.raises(ValidationError) as exc:
        root.clean()
    assert exc.value.message_dict == {
        "public_revision": ["A public revision must be approved."]
    }

    revision.review_state = Template.ReviewState.APPROVED
    revision.save()
    root.clean()

    revision.pruned_at = timezone.now()
    revision.save()
    with pytest.raises(ValidationError) as exc:
        root.clean()
    assert set(exc.value.message_dict) == {"public_revision", "shared_revision"}


@pytest.mark.django_db
def test_template_clean_allows_sharing_the_workspace_within_the_family_only(
    data_fixture,
):
    root = data_fixture.create_user_template()
    other_root = data_fixture.create_user_template()
    # A details-only revision shares the content of the revision it's based on.
    revision = data_fixture.create_user_template_revision(
        root, workspace=root.workspace
    )
    later_revision = data_fixture.create_user_template_revision(
        root, workspace=root.workspace
    )

    root.clean()
    revision.clean()
    later_revision.clean()

    for template in (
        data_fixture.create_user_template_revision(
            other_root, workspace=root.workspace
        ),
        Template(
            type=Template.Type.USER,
            name="New",
            slug="new-abc123",
            owner=root.owner,
            author=root.author,
            workspace=root.workspace,
        ),
        data_fixture.create_template(workspace=root.workspace),
    ):
        with pytest.raises(ValidationError) as exc:
            template.clean()
        assert "workspace" in exc.value.message_dict


@pytest.mark.django_db
def test_template_clean_rejects_pointers_from_revisions_and_unsaved_roots(
    data_fixture,
):
    root = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )

    revision.public_revision = revision
    with pytest.raises(ValidationError) as exc:
        revision.clean()
    assert "public_revision" in exc.value.message_dict

    unsaved = Template(
        type=Template.Type.USER,
        name="New",
        slug="new-abc123",
        owner=root.owner,
        author=root.author,
        workspace=data_fixture.create_workspace(),
        shared_revision=root,
    )
    with pytest.raises(ValidationError) as exc:
        unsaved.clean()
    assert "shared_revision" in exc.value.message_dict


@pytest.mark.django_db
def test_template_clean_rejects_pointer_to_revision_without_content(data_fixture):
    root = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )
    Template.objects.filter(id=revision.id).update(workspace=None)
    root.public_revision_id = revision.id

    with pytest.raises(ValidationError) as exc:
        root.clean()
    assert "public_revision" in exc.value.message_dict


@pytest.mark.django_db
def test_template_clean_rejects_pointer_to_revision_of_other_type(data_fixture):
    root = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(
        root, review_state=Template.ReviewState.APPROVED
    )
    # A row written without clean(), e.g. by a raw update.
    Template.objects.filter(id=revision.id).update(type=Template.Type.OFFICIAL)
    root.public_revision_id = revision.id

    with pytest.raises(ValidationError) as exc:
        root.clean()
    assert "public_revision" in exc.value.message_dict


@pytest.mark.django_db
def test_template_family_helpers(data_fixture):
    root = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(root)

    assert root.family_id == root.id
    assert revision.family_id == root.id
    assert root.get_root() == root
    assert revision.get_root() == root


@pytest.mark.django_db
def test_user_templates_require_approval_by_default():
    assert CoreHandler().get_settings().user_templates_require_approval is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_template_workspaces_are_hidden_like_official_ones(
    api_client, data_fixture
):
    staff, token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace(user=staff)
    root = data_fixture.create_user_template()
    revision = data_fixture.create_user_template_revision(root)
    template_workspace_ids = {root.workspace_id, revision.workspace_id}
    tables = [
        data_fixture.create_database_table(
            database=data_fixture.create_database_application(
                workspace=template.workspace
            )
        )
        for template in (root, revision)
    ]

    response = api_client.get(
        reverse("api:admin:workspaces:list"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert [w["id"] for w in response.json()["results"]] == [workspace.id]

    response = api_client.get(
        reverse("api:admin:workspaces:options"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert [w["id"] for w in response.json()["results"]] == [workspace.id]

    response = api_client.get(
        reverse("api:admin:dashboard:dashboard"), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["total_workspaces"] == 1

    for workspace_id in template_workspace_ids:
        response = api_client.delete(
            reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace_id}),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP"

    assert UsageHandler.calculate_storage_usage() == 1
    assert not Workspace.objects.filter(
        id__in=template_workspace_ids, storage_usage_updated_at__isnull=False
    ).exists()

    TableUsageHandler.update_tables_usage()
    assert not TableUsage.objects.filter(table__in=tables).exists()
