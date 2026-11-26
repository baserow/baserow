from django.core.management import CommandError, call_command
from django.db.migrations import Migration

import pytest

from baserow.core.models import Template, Workspace
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.receivers import (
    rebuild_user_templates_after_migrate,
)
from tests.baserow.core.user_templates.utils import (
    add_source_leftovers,
    assert_source_leftovers_left_out,
    request_download,
    store_template_archive,
)

pytestmark = [
    pytest.mark.import_export_workspace,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("use_tmp_media_root"),
]


def create_template_copied_before_a_fix(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(name="Content")
    database = data_fixture.create_database_application(workspace=workspace)
    add_source_leftovers(data_fixture, database, user)
    template = data_fixture.create_user_template(user=user, workspace=workspace)
    revision = data_fixture.create_user_template_revision(template, workspace=workspace)
    return template, revision, store_template_archive(revision)


def test_rebuild_user_templates_cleans_the_content_copied_before_a_fix(
    data_fixture,
):
    template, revision, archive = create_template_copied_before_a_fix(data_fixture)
    old_workspace_id = template.workspace_id
    other, _, _ = create_template_copied_before_a_fix(data_fixture)

    call_command("rebuild_user_templates", "--template", template.id)

    rebuilt = Template.objects.get(id=template.id)
    revisions = Template.objects.filter(id__in=[template.id, revision.id])
    assert {(t.workspace_id, t.archive.name) for t in revisions} == {
        (rebuilt.workspace_id, None)
    }
    database = rebuilt.workspace.application_set.get().specific
    assert_source_leftovers_left_out(database)
    assert not Workspace.objects_and_trash.filter(id=old_workspace_id).exists()
    assert not get_default_storage().exists(archive)
    assert Template.objects.get(id=other.id).workspace_id == other.workspace_id


def test_rebuild_user_templates_skips_a_template_with_a_running_job(data_fixture):
    template, revision, archive = create_template_copied_before_a_fix(data_fixture)
    request_download(template.owner, template, revision)
    workspace_count = Workspace.objects_and_trash.count()

    with pytest.raises(CommandError):
        call_command("rebuild_user_templates", "--all")

    assert Template.objects.get(id=revision.id).archive.name == archive
    assert Workspace.objects_and_trash.count() == workspace_count


@pytest.mark.parametrize(
    "plan,rebuilt",
    [
        ([(Migration("0146_rebuild_user_templates", "core"), False)], True),
        ([(Migration("0146_rebuild_user_templates", "core"), True)], False),
        ([(Migration("0145_settings_allow_user_templates", "core"), False)], False),
    ],
)
def test_migrate_rebuilds_user_templates_once(data_fixture, plan, rebuilt):
    template, _, _ = create_template_copied_before_a_fix(data_fixture)

    rebuild_user_templates_after_migrate(sender=None, plan=plan)

    workspace_id = Template.objects.get(id=template.id).workspace_id
    assert (workspace_id != template.workspace_id) is rebuilt
