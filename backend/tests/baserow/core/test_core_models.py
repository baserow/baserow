from datetime import datetime, timezone
from uuid import UUID

from django.db import IntegrityError, connection, transaction
from django.utils import timezone as django_timezone

import pytest
from freezegun import freeze_time

from baserow.contrib.database.models import Database
from baserow.core.models import (
    Template,
    TemplateLinkAccess,
    TemplateListingState,
    TemplateTypes,
    Workspace,
    WorkspaceUser,
    official_template_uuid,
)


@pytest.mark.django_db
def test_created_and_updated_on_mixin():
    with freeze_time("2020-01-01 12:00"):
        workspace = Workspace.objects.create(name="Workspace")

    assert workspace.created_on == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)
    assert workspace.updated_on == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)

    with freeze_time("2020-01-02 12:00"):
        workspace.name = "Workspace2"
        workspace.save()

    assert workspace.created_on == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)
    assert workspace.updated_on == datetime(2020, 1, 2, 12, 00, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_workspace_user_get_next_order(data_fixture):
    user = data_fixture.create_user()

    assert WorkspaceUser.get_last_order(user) == 1

    workspace_user_1 = data_fixture.create_user_workspace(order=0)
    workspace_user_2_1 = data_fixture.create_user_workspace(order=10)
    data_fixture.create_user_workspace(user=workspace_user_2_1.user, order=11)

    assert WorkspaceUser.get_last_order(workspace_user_1.user) == 1
    assert WorkspaceUser.get_last_order(workspace_user_2_1.user) == 12


@pytest.mark.django_db
def test_application_content_type_init(data_fixture):
    workspace = data_fixture.create_workspace()
    database = Database.objects.create(name="Test 1", order=0, workspace=workspace)

    assert database.content_type.app_label == "database"
    assert database.content_type.model == "database"


@pytest.mark.django_db
def test_core_models_hierarchy(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    app = data_fixture.create_database_application(workspace=workspace, name="Test 1")

    assert app.get_parent() == app.application_ptr
    assert app.get_root() == workspace

    assert workspace.get_parent() is None
    assert workspace.get_root() == workspace


def test_official_template_uuid_never_changes():
    # The namespace is permanent: the same official template must keep the same
    # uuid on every instance and across releases.
    assert official_template_uuid("project-tracker") == UUID(
        "914af5fe-6f50-51ec-8493-afde6b4ce39e"
    )


@pytest.mark.django_db
def test_template_defaults(data_fixture):
    template = data_fixture.create_template()

    assert template.template_type == TemplateTypes.OFFICIAL
    assert template.listing_state == TemplateListingState.PUBLIC
    assert template.author is None
    assert template.uuid is None
    assert template.state_before_block is None
    assert template.install_count == 0
    assert template.created_on is not None


@pytest.mark.django_db
def test_template_row_inserted_without_new_columns_gets_official_defaults():
    # The previous application version inserts templates without the new columns.
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core_template (name, slug, icon, export_hash, keywords) "
            "VALUES ('Old', 'old', 'document', '', '') RETURNING id"
        )
        template_id = cursor.fetchone()[0]

    template = Template.objects.get(id=template_id)
    assert template.template_type == TemplateTypes.OFFICIAL
    assert template.listing_state == TemplateListingState.PUBLIC
    assert template.description == ""
    assert template.state_note == ""
    assert template.install_count == 0
    assert template.created_on is not None
    assert template.updated_on is not None


@pytest.mark.django_db
def test_template_queryset_official_and_user_templates(data_fixture):
    official = data_fixture.create_template()
    user_template = data_fixture.create_user_template()

    assert list(Template.objects.official()) == [official]
    assert list(Template.objects.user_templates()) == [user_template]
    assert user_template.listing_state == TemplateListingState.PRIVATE
    assert user_template.workspace.users.count() == 0


@pytest.mark.django_db(transaction=True)
def test_user_template_requires_author(data_fixture):
    with pytest.raises(IntegrityError), transaction.atomic():
        data_fixture.create_template(template_type=TemplateTypes.USER)

    template = data_fixture.create_template()
    template.template_type = TemplateTypes.USER
    with pytest.raises(IntegrityError), transaction.atomic():
        template.save()


@pytest.mark.django_db
def test_template_marked_for_deletion_hidden_by_default_manager(data_fixture):
    template = data_fixture.create_template()
    marked = data_fixture.create_user_template(
        marked_for_deletion_at=django_timezone.now()
    )

    assert list(Template.objects.all()) == [template]
    assert set(Template.objects_and_trash.all()) == {template, marked}
    assert list(Template.objects_and_trash.user_templates()) == [marked]


@pytest.mark.django_db
def test_template_deleted_with_author(data_fixture):
    author = data_fixture.create_user()
    template = data_fixture.create_user_template(author=author)
    other_user = data_fixture.create_user()
    TemplateLinkAccess.objects.create(template=template, user=other_user)

    author.delete()

    assert not Template.objects_and_trash.filter(id=template.id).exists()
    assert not TemplateLinkAccess.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_template_link_access_unique_per_user(data_fixture):
    template = data_fixture.create_user_template()
    user = data_fixture.create_user()
    TemplateLinkAccess.objects.create(template=template, user=user)

    with pytest.raises(IntegrityError), transaction.atomic():
        TemplateLinkAccess.objects.create(template=template, user=user)


@pytest.mark.django_db
def test_workspace_has_template_counts_only_live_official_templates(data_fixture):
    official = data_fixture.create_template()
    user_template = data_fixture.create_user_template()
    marked = data_fixture.create_template(marked_for_deletion_at=django_timezone.now())
    plain_workspace = data_fixture.create_workspace()

    assert official.workspace.has_template() is True
    assert user_template.workspace.has_template() is False
    assert marked.workspace.has_template() is False
    assert plain_workspace.has_template() is False
