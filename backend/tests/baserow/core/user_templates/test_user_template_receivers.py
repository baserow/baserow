from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

import pytest
from freezegun import freeze_time

from baserow.core.admin.users.handler import UserAdminHandler
from baserow.core.jobs.constants import JOB_PENDING, JOB_STARTED
from baserow.core.models import Template, Workspace
from baserow.core.storage import get_default_storage
from baserow.core.user.handler import UserHandler
from baserow.core.user_templates.models import (
    CreateUserTemplateJob,
    UserTemplateContentToDelete,
)
from tests.baserow.core.user_templates.utils import (
    ICON,
    create_content,
    purge_after_the_grace_period,
    store_archive,
)

User = get_user_model()


@pytest.mark.django_db
def test_deleting_user_marks_their_user_templates_for_deletion(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    template = data_fixture.create_user_template(user=user)
    revision = data_fixture.create_user_template_revision(template)
    other_template = data_fixture.create_user_template(user=other_user)

    user.delete()

    template.refresh_from_db()
    assert template.owner is None
    assert template.author is None
    assert template.marked_for_deletion_at is not None
    revision.refresh_from_db()
    assert revision.marked_for_deletion_at is None
    other_template.refresh_from_db()
    assert other_template.owner == other_user
    assert other_template.marked_for_deletion_at is None


@pytest.mark.django_db
def test_deleting_user_keeps_earlier_deletion_mark(data_fixture):
    user = data_fixture.create_user()
    marked_on = timezone.now() - timedelta(days=1)
    template = data_fixture.create_user_template(
        user=user, marked_for_deletion_at=marked_on
    )

    user.delete()

    template.refresh_from_db()
    assert template.marked_for_deletion_at == marked_on


@pytest.mark.django_db
def test_deleting_user_doesnt_touch_official_templates(data_fixture):
    user = data_fixture.create_user()
    official = data_fixture.create_template()

    user.delete()

    official.refresh_from_db()
    assert official.marked_for_deletion_at is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_delete_user_owning_a_user_template(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    user = data_fixture.create_user()
    template = data_fixture.create_user_template(user=user)

    UserAdminHandler().delete_user(admin, user.id)

    assert not User.objects.filter(id=user.id).exists()
    template.refresh_from_db()
    assert template.owner is None
    assert template.marked_for_deletion_at is not None


@pytest.mark.django_db
def test_scheduled_user_deletion_deletes_template_owner_and_other_user(
    data_fixture,
):
    owner = data_fixture.create_user()
    other_user = data_fixture.create_user()
    template = data_fixture.create_user_template(user=owner)

    for user in (owner, other_user):
        user.profile.to_be_deleted = True
        user.profile.save(update_fields=("to_be_deleted",))

    handler = UserHandler()
    with freeze_time("2020-01-01 12:00"):
        handler.update_last_login(owner)
        handler.update_last_login(other_user)

    with freeze_time("2020-01-07 12:00"):
        handler.delete_expired_users_and_related_workspaces_if_last_admin(
            grace_delay=timedelta(days=3)
        )

    assert not User.objects.filter(id__in=[owner.id, other_user.id]).exists()
    template = Template.objects.get(id=template.id)
    assert template.owner is None
    assert template.marked_for_deletion_at is not None


def create_template_with_content(data_fixture, user):
    workspace, archive = create_content(data_fixture, "Template")
    template = data_fixture.create_user_template(
        user=user, workspace=workspace, archive=archive, icon=ICON
    )
    return template, workspace, archive


def assert_template_and_content_removed(template, workspace, archive):
    assert not Template.objects.filter(id=template.id).exists()
    assert not Workspace.objects_and_trash.filter(id=workspace.id).exists()
    assert not get_default_storage().exists(archive)
    assert not UserTemplateContentToDelete.objects.exists()


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("use_tmp_media_root")
def test_purge_removes_the_templates_of_a_deleted_user(data_fixture):
    user = data_fixture.create_user()
    source_workspace = data_fixture.create_workspace(user=user)
    template, workspace, archive = create_template_with_content(data_fixture, user)
    other_template, other_workspace, other_archive = create_template_with_content(
        data_fixture, data_fixture.create_user()
    )

    user.delete()
    assert Template.objects.get(id=template.id).marked_for_deletion_at is not None
    purge_after_the_grace_period()

    assert_template_and_content_removed(template, workspace, archive)
    # The workspace of the deleted user stays until its own deletion.
    assert Workspace.objects.filter(id=source_workspace.id).exists()
    assert Template.objects.get(id=other_template.id).marked_for_deletion_at is None
    assert Workspace.objects.filter(id=other_workspace.id).exists()
    assert get_default_storage().exists(other_archive)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("use_tmp_media_root")
@override_settings(DEBUG=True)
def test_deactivating_or_scheduling_the_deletion_of_a_user_keeps_their_templates(
    data_fixture,
):
    admin = data_fixture.create_user(is_staff=True)
    deactivated = data_fixture.create_user()
    scheduled = data_fixture.create_user()
    templates = [
        create_template_with_content(data_fixture, deactivated),
        create_template_with_content(data_fixture, scheduled),
    ]

    with transaction.atomic():
        UserAdminHandler().update_user(admin, deactivated.id, is_active=False)
        UserHandler().schedule_user_deletion(scheduled)
    purge_after_the_grace_period()

    for template, workspace, archive in templates:
        template.refresh_from_db()
        assert template.marked_for_deletion_at is None
        assert template.owner_id is not None
        assert Workspace.objects.filter(id=workspace.id).exists()
        assert get_default_storage().exists(archive)


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("use_tmp_media_root")
@pytest.mark.parametrize("state", [JOB_PENDING, JOB_STARTED])
def test_deleting_a_user_while_their_template_is_updated(data_fixture, state):
    user = data_fixture.create_user()
    template, workspace, archive = create_template_with_content(data_fixture, user)
    # What the update copied so far.
    job_workspace = data_fixture.create_workspace(name="Copy")
    job_archive = store_archive("copy.zip")
    job = CreateUserTemplateJob.objects.create(
        user=user,
        state=state,
        name=template.name,
        icon=ICON,
        template=template,
        base_revision=template,
        template_workspace=job_workspace,
        archive_name=job_archive,
    )

    user.delete()

    assert not CreateUserTemplateJob.objects.filter(id=job.id).exists()
    assert not Workspace.objects_and_trash.filter(id=job_workspace.id).exists()
    assert not get_default_storage().exists(job_archive)
    assert Template.objects.get(id=template.id).marked_for_deletion_at is not None

    purge_after_the_grace_period()

    assert_template_and_content_removed(template, workspace, archive)
