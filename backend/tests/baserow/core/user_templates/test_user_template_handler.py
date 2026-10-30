import os
import re
import threading
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_PENDING, JOB_STARTED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import JOB_STATES_ENDED
from baserow.core.models import Template, Workspace
from baserow.core.subjects import UserSubjectType
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_templates.constants import (
    USER_TEMPLATE_ICON_MAX_LENGTH,
    UserTemplateState,
)
from baserow.core.user_templates.exceptions import (
    InvalidTemplateCategory,
    InvalidTemplateIcon,
    TemplateChangedDuringUpdate,
    TemplateSlugGenerationFailed,
)
from baserow.core.user_templates.handler import (
    UserTemplateHandler,
    generate_template_slug,
)
from baserow.core.user_templates.models import CreateUserTemplateJob
from tests.baserow.core.user_templates.utils import create_source, start_job

TEST_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "../../../tests/templates")
SLUG_SUFFIX_PATH = "baserow.core.user_templates.handler.generate_slug_suffix"


def create_root(data_fixture, **kwargs):
    kwargs.setdefault("owner", data_fixture.create_user())
    kwargs.setdefault("name", "My template")
    kwargs.setdefault("description", "What it does")
    kwargs.setdefault("icon", "iconoir-view-grid")
    if "category_ids" not in kwargs:
        kwargs["category_ids"] = [data_fixture.create_template_category().id]
    kwargs.setdefault("workspace", data_fixture.create_workspace())
    return UserTemplateHandler().create_template_root(**kwargs)


def test_user_template_icon_max_length_fits_the_icon_column():
    assert USER_TEMPLATE_ICON_MAX_LENGTH == Template._meta.get_field("icon").max_length


@pytest.mark.parametrize(
    "icon",
    ["fa-table", "iconoir-", "iconoir-table extra", "iconoir-" + "a" * 25, ""],
)
def test_validate_icon_and_categories_rejects_an_invalid_icon(icon):
    with pytest.raises(InvalidTemplateIcon):
        UserTemplateHandler().validate_icon_and_categories(icon, [])


def test_generate_template_slug_format():
    for _ in range(50):
        slug = generate_template_slug("My Great Template!")
        assert re.fullmatch(r"my-great-template-[a-z0-9]{6}", slug)
        assert re.search(r"[0-9]", slug.rsplit("-", 1)[1])


def test_generate_template_slug_truncates_long_names():
    slug = generate_template_slug("word " * 30)

    assert len(slug) <= Template._meta.get_field("slug").max_length
    base = slug.rsplit("-", 1)[0]
    assert base.startswith("word-word")
    assert not base.endswith("-")


def test_generate_template_slug_without_ascii_characters():
    assert re.fullmatch(r"template-[a-z0-9]{6}", generate_template_slug("模板"))
    assert re.fullmatch(r"template-[a-z0-9]{6}", generate_template_slug("!!!"))


@pytest.mark.django_db
def test_create_template_root(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    category_1 = data_fixture.create_template_category()
    category_2 = data_fixture.create_template_category()

    template = create_root(
        data_fixture,
        owner=user,
        name="Sales pipeline",
        description="Track deals",
        icon="iconoir-coins",
        category_ids=[category_1.id, category_2.id],
        workspace=workspace,
    )

    template = Template.objects.get(id=template.id)
    assert template.type == Template.Type.USER
    assert template.owner == user
    assert template.author == user
    assert template.version == 1
    assert template.root is None
    assert template.name == "Sales pipeline"
    assert template.description == "Track deals"
    assert template.icon == "iconoir-coins"
    assert template.workspace == workspace
    assert re.fullmatch(r"sales-pipeline-[a-z0-9]{6}", template.slug)
    assert set(template.categories.all()) == {category_1, category_2}
    assert template.review_state == Template.ReviewState.NOT_SUBMITTED
    assert template.public_revision is None
    assert template.shared_revision is None
    assert template.private_link_token is None
    assert not template.archive
    assert UserTemplateHandler().get_template_state(template) == (
        UserTemplateState.PRIVATE,
        None,
    )


@pytest.mark.django_db
def test_create_template_root_opens_a_workspace_checked_before(data_fixture):
    # Anyone can check the workspace while the job copies into it, e.g. through
    # the applications list of its id. The answer is cached in that process.
    workspace = data_fixture.create_workspace()
    owner = data_fixture.create_user()
    assert not Workspace.objects.get(id=workspace.id).has_openable_template(owner)

    create_root(data_fixture, owner=owner, workspace=workspace)

    # The next request loads the workspace again.
    assert Workspace.objects.get(id=workspace.id).has_openable_template(owner)


@pytest.mark.django_db
def test_create_template_root_refuses_a_deleted_owner(data_fixture):
    owner = data_fixture.create_user()
    category = data_fixture.create_template_category()

    def delete_owner(*args, **kwargs):
        # Deleted after the template was validated.
        type(owner).objects.filter(id=owner.id).delete()

    with patch.object(Template, "full_clean", delete_owner):
        with pytest.raises(UserNotFound):
            create_root(data_fixture, owner=owner, category_ids=[category.id])

    assert not Template.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_deleting_the_owner_waits_for_a_template_being_created(data_fixture):
    owner = data_fixture.create_user()
    category = data_fixture.create_template_category()
    workspace = data_fixture.create_workspace()
    created = threading.Event()
    commit = threading.Event()
    errors = []

    def in_thread(function):
        def run():
            try:
                function()
            except Exception as error:
                errors.append(error)
            finally:
                connection.close()

        thread = threading.Thread(target=run)
        thread.start()
        return thread

    def create():
        with transaction.atomic():
            create_root(
                data_fixture,
                owner=owner,
                category_ids=[category.id],
                workspace=workspace,
            )
            created.set()
            commit.wait(timeout=10)

    creator = in_thread(create)
    assert created.wait(timeout=10)
    deleter = in_thread(lambda: type(owner).objects.get(id=owner.id).delete())
    deleter.join(timeout=1)
    assert deleter.is_alive()

    commit.set()
    creator.join(timeout=10)
    deleter.join(timeout=10)

    assert errors == []
    template = Template.objects.get()
    assert template.owner_id is None
    assert template.marked_for_deletion_at is not None


@pytest.mark.django_db
def test_create_template_root_stores_archive(data_fixture, tmpdir):
    with override_settings(MEDIA_ROOT=str(tmpdir)):
        template = create_root(data_fixture, archive=ContentFile(b"zip", "a.zip"))

        template.refresh_from_db()
        assert template.archive.name.startswith("template-revisions/")
        assert template.archive.read() == b"zip"


@pytest.mark.django_db
def test_create_template_root_rejects_an_invalid_icon(data_fixture):
    with pytest.raises(InvalidTemplateIcon):
        create_root(data_fixture, icon="fa-table")

    assert not Template.objects.exists()


@pytest.mark.django_db
def test_create_template_root_rejects_missing_or_unknown_categories(data_fixture):
    category = data_fixture.create_template_category()

    with pytest.raises(InvalidTemplateCategory):
        create_root(data_fixture, category_ids=[])

    with pytest.raises(InvalidTemplateCategory):
        create_root(data_fixture, category_ids=[category.id, category.id + 100])

    assert not Template.objects.exists()


@pytest.mark.django_db
def test_create_template_root_without_categories_on_the_instance(data_fixture):
    template = create_root(data_fixture, category_ids=[])

    assert list(template.categories.all()) == []


@pytest.mark.django_db
def test_create_template_root_runs_full_clean(data_fixture):
    with pytest.raises(ValidationError) as exc_info:
        create_root(data_fixture, name="a" * 65)
    assert "name" in exc_info.value.message_dict

    with pytest.raises(ValidationError):
        create_root(data_fixture, name="")

    used_workspace = data_fixture.create_template().workspace
    with pytest.raises(ValidationError):
        create_root(data_fixture, workspace=used_workspace)

    assert Template.objects.user().count() == 0


@pytest.mark.django_db
def test_create_template_root_retries_on_slug_collision(data_fixture):
    data_fixture.create_template(slug="taken-a1b2c3")

    with patch(SLUG_SUFFIX_PATH, side_effect=["a1b2c3", "d4e5f6"]):
        template = create_root(data_fixture, name="Taken")

    assert template.slug == "taken-d4e5f6"
    assert Template.objects.get(id=template.id).categories.count() == 1


@pytest.mark.django_db
def test_create_template_root_gives_up_after_three_collisions(data_fixture):
    data_fixture.create_template(slug="taken-a1b2c3")

    with (
        patch(SLUG_SUFFIX_PATH, return_value="a1b2c3") as suffix_mock,
        pytest.raises(TemplateSlugGenerationFailed),
    ):
        create_root(data_fixture, name="Taken")

    assert suffix_mock.call_count == 3
    assert Template.objects.user().count() == 0


@pytest.mark.django_db
def test_create_template_root_reraises_other_integrity_errors(data_fixture):
    with (
        patch.object(Template, "save", side_effect=IntegrityError("other")) as save,
        pytest.raises(IntegrityError),
    ):
        create_root(data_fixture)

    assert save.call_count == 1


def revision_kwargs(data_fixture, root, **kwargs):
    kwargs.setdefault("user", root.owner)
    kwargs.setdefault("base_revision", root)
    kwargs.setdefault("name", "Next")
    kwargs.setdefault("description", "")
    kwargs.setdefault("icon", "iconoir-view-grid")
    kwargs.setdefault("category_ids", [data_fixture.create_template_category().id])
    kwargs.setdefault("workspace", data_fixture.create_workspace())
    return {"root": root, **kwargs}


@pytest.mark.django_db
def test_create_template_revision_runs_full_clean(data_fixture):
    root = data_fixture.create_user_template()
    handler = UserTemplateHandler()

    with pytest.raises(ValidationError) as exc_info:
        handler.create_template_revision(
            **revision_kwargs(data_fixture, root, name="a" * 65)
        )
    assert "name" in exc_info.value.message_dict

    with pytest.raises(ValidationError):
        handler.create_template_revision(**revision_kwargs(data_fixture, root, name=""))

    assert not Template.objects.filter(root=root).exists()


@pytest.mark.django_db(transaction=True)
def test_create_template_revision_waits_for_a_concurrent_commit(
    data_fixture, test_thread
):
    root = data_fixture.create_user_template()
    handler = UserTemplateHandler()
    first = revision_kwargs(data_fixture, root, name="First")
    concurrent = revision_kwargs(data_fixture, root, name="Concurrent")
    validate_icon_and_categories = UserTemplateHandler.validate_icon_and_categories
    calls = []
    outcome = {}

    def commit_concurrently():
        try:
            handler.create_template_revision(**concurrent)
            outcome["concurrent"] = "committed"
        except TemplateChangedDuringUpdate:
            outcome["concurrent"] = "changed"
        finally:
            connection.close()

    with test_thread(commit_concurrently) as thread:

        def validate_with_a_concurrent_commit(self, *args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                thread.start()
                # It waits for the lock on the root, held until the first commits,
                # and then sees that the template changed.
                assert not thread.thread_stopped.wait(0.3)
            return validate_icon_and_categories(self, *args, **kwargs)

        with patch.object(
            UserTemplateHandler,
            "validate_icon_and_categories",
            validate_with_a_concurrent_commit,
        ):
            handler.create_template_revision(**first)

    assert outcome == {"concurrent": "changed"}
    assert list(Template.objects.filter(root=root).values_list("name", flat=True)) == [
        "First"
    ]


@pytest.mark.django_db
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_sync_templates_installs_official_template_next_to_user_slug(
    data_fixture, tmpdir
):
    user_template = create_root(data_fixture, name="Example template")
    assert user_template.slug.startswith("example-template-")

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    CoreHandler().sync_templates(storage=storage)

    official = Template.objects.official().get(slug="example-template")
    assert official.workspace.application_set.count() == 1
    user_template.refresh_from_db()
    assert user_template.name == "Example template"
    assert Template.objects.user().get() == user_template


@pytest.mark.django_db
def test_list_own_templates(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    now = timezone.now()

    older = data_fixture.create_user_template(user=user)
    newer = data_fixture.create_user_template(user=user)
    same_time = data_fixture.create_user_template(user=user)
    data_fixture.create_user_template_revision(newer)
    newer_latest = data_fixture.create_user_template_revision(newer)
    Template.objects.filter(id=older.id).update(created_on=now - timedelta(days=2))
    Template.objects.filter(id__in=[newer.id, same_time.id]).update(
        created_on=now - timedelta(days=1)
    )
    Template.objects.filter(id__in=[newer_latest.id, same_time.id]).update(
        created_on=now
    )
    data_fixture.create_user_template(user=other_user)
    marked = data_fixture.create_user_template(user=user, marked_for_deletion_at=now)
    data_fixture.create_user_template_revision(marked)
    data_fixture.create_template()

    templates = list(
        CoreHandler().list_templates(user, template_type="user", owned=True)
    )

    # The latest revision of each template, ordered by its creation, then by id.
    assert templates == [newer_latest, same_time, older]
    assert [template.get_root() for template in templates] == [
        newer,
        same_time,
        older,
    ]


@pytest.mark.django_db
def test_list_templates_puts_never_updated_templates_last(data_fixture):
    user = data_fixture.create_user()
    never_updated = data_fixture.create_template()
    official = data_fixture.create_template()
    own = data_fixture.create_user_template(user=user)
    Template.objects.filter(id=never_updated.id).update(updated_on=None)

    templates = list(CoreHandler().list_templates(user))

    assert templates == [own, official, never_updated]


@pytest.mark.django_db
def test_list_templates_owned_by_an_anonymous_user(data_fixture):
    data_fixture.create_template()

    assert list(CoreHandler().list_templates(AnonymousUser(), owned=True)) == []


@pytest.mark.django_db
def test_list_listed_templates(data_fixture):
    user = data_fixture.create_user()
    official = data_fixture.create_template()
    data_fixture.create_user_template(user=user)
    own = data_fixture.create_user_template(user=user)
    # The listed revision of the actor's own template isn't its root.
    listed_revision = data_fixture.create_user_template_revision(own)
    data_fixture.set_user_template_state(own, "public", revision=listed_revision)
    other = data_fixture.set_user_template_state(
        data_fixture.create_user_template(), "public"
    )
    data_fixture.create_user_template_revision(own)
    for state in ["public_blocked", "marked"]:
        template = data_fixture.create_user_template()
        data_fixture.set_user_template_state(template, "public")
        data_fixture.set_user_template_state(template, state)

    def listed(actor):
        return list(CoreHandler().list_templates(actor, "user", listed=True))

    # The listed revision, not the latest one, and the actor's own first.
    assert listed(user) == [listed_revision, other]
    assert listed(AnonymousUser()) == [other, listed_revision]
    # Everybody can open an official template.
    assert official in CoreHandler().list_templates(user, listed=True)


@pytest.mark.django_db
def test_listed_category_filter_uses_listed_revision(data_fixture):
    before, after = (data_fixture.create_template_category() for _ in range(2))
    template = data_fixture.create_user_template(category=before)
    revision = data_fixture.create_user_template_revision(template, category=after)
    data_fixture.set_user_template_state(template, "public", revision=revision)

    def listed(category):
        return list(
            CoreHandler().list_templates(
                AnonymousUser(), listed=True, category_id=category.id
            )
        )

    assert listed(before) == []
    assert listed(after) == [revision]


@pytest.mark.django_db
def test_get_own_template(data_fixture):
    user = data_fixture.create_user()
    root = data_fixture.create_user_template(user=user)
    revision = data_fixture.create_user_template_revision(root)
    blocked = data_fixture.create_user_template(user=user, blocked_at=timezone.now())
    marked = data_fixture.create_user_template(
        user=user, marked_for_deletion_at=timezone.now()
    )
    staff = data_fixture.create_user(is_staff=True)
    handler = UserTemplateHandler()

    assert handler.get_own_template(user, root.id) == root
    assert handler.get_own_template(user, blocked.id) == blocked

    for template_user, template_id in [
        (data_fixture.create_user(), root.id),
        (staff, root.id),
        (user, revision.id),
        (user, marked.id),
        (user, data_fixture.create_template().id),
        (user, 0),
    ]:
        with pytest.raises(TemplateDoesNotExist):
            handler.get_own_template(template_user, template_id)


@pytest.mark.django_db
def test_get_latest_revision(data_fixture):
    handler = UserTemplateHandler()
    root = data_fixture.create_user_template()
    assert handler.get_latest_revision(root) == root

    data_fixture.create_user_template_revision(root)
    latest = data_fixture.create_user_template_revision(root)
    data_fixture.create_user_template_revision(data_fixture.create_user_template())

    assert handler.get_latest_revision(root) == latest


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,state,reason,needs_review",
    [
        (["private"], UserTemplateState.PRIVATE, None, False),
        (["in_review"], UserTemplateState.IN_REVIEW, None, False),
        (["rejected"], UserTemplateState.REJECTED, "Reason", True),
        # An edit of a rejected template is still rejected.
        (["rejected", "private"], UserTemplateState.REJECTED, "Reason", True),
        (["withdrawn_rejected"], UserTemplateState.PRIVATE, None, True),
        (["private", "in_review"], UserTemplateState.IN_REVIEW, None, False),
        (["public", "private"], UserTemplateState.PUBLIC, None, False),
        (["rejected", "public"], UserTemplateState.PUBLIC, None, False),
        # An edit of a listed template in review or rejected shows that, while
        # the listed revision stays listed.
        (["public", "in_review"], UserTemplateState.IN_REVIEW, None, False),
        (["public", "rejected"], UserTemplateState.REJECTED, "Reason", True),
        (["rejected", "blocked"], UserTemplateState.BLOCKED, "Spam", False),
        (["public_blocked"], UserTemplateState.BLOCKED, "Spam", False),
    ],
)
def test_get_template_state(data_fixture, revision_states, state, reason, needs_review):
    handler = UserTemplateHandler()
    root = data_fixture.create_user_template(blocked_reason="Spam")
    revision = root
    for index, revision_state in enumerate(revision_states):
        if index:
            revision = data_fixture.create_user_template_revision(root)
        data_fixture.set_user_template_state(root, revision_state, revision)

    # The state the admin list filters and sorts on is the same, in SQL.
    annotated = handler.list_templates_for_admin().get(id=revision.id)
    assert annotated.admin_state == state
    for latest in [handler.get_latest_revision(root), annotated]:
        assert handler.get_template_state(latest) == (state, reason)
        assert handler.needs_review(latest, require_approval=False) is needs_review
        # With approval on, a private template needs a review too.
        assert handler.needs_review(latest, require_approval=True) is (
            needs_review or state == UserTemplateState.PRIVATE
        )
        # A blocked template isn't listed, even with a public revision.
        assert handler.is_listed(latest) is ("public" in revision_states)


@pytest.mark.django_db
def test_get_template_for_deletion(data_fixture):
    owner = data_fixture.create_user()
    staff = data_fixture.create_user(is_staff=True)
    root = data_fixture.create_user_template(user=owner)
    revision = data_fixture.create_user_template_revision(root)
    blocked = data_fixture.create_user_template(user=owner, blocked_at=timezone.now())
    marked = data_fixture.create_user_template(
        user=owner, marked_for_deletion_at=timezone.now()
    )
    official = data_fixture.create_template()
    handler = UserTemplateHandler()

    with transaction.atomic():
        assert handler.get_template_for_deletion(owner, root.id) == root
        assert handler.get_template_for_deletion(owner, blocked.id) == blocked
        # An instance admin can delete the templates of others.
        assert handler.get_template_for_deletion(staff, root.id) == root

    for user, template_id in [
        (data_fixture.create_user(), root.id),
        (owner, revision.id),
        (staff, revision.id),
        (owner, marked.id),
        (staff, marked.id),
        (owner, official.id),
        (staff, official.id),
        (staff, 0),
    ]:
        with transaction.atomic(), pytest.raises(TemplateDoesNotExist):
            handler.get_template_for_deletion(user, template_id)


@pytest.mark.django_db
def test_get_template_for_deletion_locks_the_root(data_fixture):
    owner = data_fixture.create_user()
    root = data_fixture.create_user_template(user=owner)

    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        UserTemplateHandler().get_template_for_deletion(owner, root.id)

    selects = [
        query["sql"]
        for query in queries.captured_queries
        if 'FROM "core_template"' in query["sql"]
    ]
    assert len(selects) == 1
    assert selects[0].endswith("FOR UPDATE")


def create_update_job(root, state, **kwargs):
    return CreateUserTemplateJob.objects.create(
        user=root.owner,
        state=state,
        template=root,
        base_revision=root,
        name="Update",
        icon="iconoir-view-grid",
        **kwargs,
    )


@pytest.mark.django_db
def test_mark_template_for_deletion_cancels_its_uncommitted_updates(data_fixture):
    owner = data_fixture.create_user()
    root = data_fixture.create_user_template(user=owner)
    other_root = data_fixture.create_user_template(user=owner)
    pending = create_update_job(root, JOB_PENDING)
    running = create_update_job(root, JOB_STARTED)
    committed = create_update_job(
        root, JOB_STARTED, revision=data_fixture.create_user_template_revision(root)
    )
    ended = [create_update_job(root, state) for state in JOB_STATES_ENDED]
    other_template = create_update_job(other_root, JOB_PENDING)
    handler = UserTemplateHandler()

    with (
        patch.object(
            JobHandler, "cancel_job", wraps=JobHandler.cancel_job
        ) as cancel_job,
        transaction.atomic(),
    ):
        handler.mark_template_for_deletion(
            handler.get_template_for_deletion(owner, root.id)
        )

    # Only the updates that can still commit are cancelled, the others aren't
    # even tried.
    assert sorted(call.args[0].id for call in cancel_job.call_args_list) == sorted(
        [pending.id, running.id]
    )
    states = dict(CreateUserTemplateJob.objects.values_list("id", "state"))
    assert states[pending.id] == JOB_CANCELLED
    assert states[running.id] == JOB_CANCELLED
    assert states[committed.id] == JOB_STARTED
    assert [states[job.id] for job in ended] == list(JOB_STATES_ENDED)
    assert states[other_template.id] == JOB_PENDING

    root.refresh_from_db()
    assert root.marked_for_deletion_at is not None
    other_root.refresh_from_db()
    assert other_root.marked_for_deletion_at is None


@pytest.mark.django_db
def test_mark_template_for_deletion_ignores_an_update_that_ended_meanwhile(
    data_fixture,
):
    owner = data_fixture.create_user()
    root = data_fixture.create_user_template(user=owner)
    job = create_update_job(root, JOB_STARTED)
    handler = UserTemplateHandler()

    # The job ended, or committed, between the query and its lock.
    with (
        patch.object(
            JobHandler, "cancel_job", side_effect=JobNotCancellable()
        ) as cancel_job,
        transaction.atomic(),
    ):
        handler.mark_template_for_deletion(
            handler.get_template_for_deletion(owner, root.id)
        )

    cancel_job.assert_called_once()
    assert Template.objects.get(id=root.id).marked_for_deletion_at is not None
    assert CreateUserTemplateJob.objects.get(id=job.id).state == JOB_STARTED


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
def test_install_template_content_applies_the_content_rules(
    data_fixture, use_tmp_media_root
):
    source = create_source(data_fixture)
    owner = source["user"]
    file_field = data_fixture.create_file_field(table=source["table"], name="File")
    user_file = UserFileHandler().upload_user_file(
        owner, "notes.txt", BytesIO(b"Notes")
    )
    RowHandler().create_row(
        owner,
        source["table"],
        values={file_field.db_column: [{"name": user_file.name}]},
    )
    job = start_job(
        owner,
        source["workspace"],
        [source["database"], source["builder"], source["dashboard"]],
    )
    revision = Template.objects.get(id=job.template_id)
    installer = data_fixture.create_user()
    target = data_fixture.create_workspace(user=installer)
    configs = []
    serialize_applications = UserTemplateHandler.serialize_applications
    import_applications = CoreHandler.import_applications_to_workspace

    def serialize_spy(self, applications, config, *args, **kwargs):
        configs.append(config)
        return serialize_applications(self, applications, config, *args, **kwargs)

    def import_spy(self, workspace, serialized, files_buffer, config, *args, **kwargs):
        configs.append(config)
        return import_applications(
            self, workspace, serialized, files_buffer, config, *args, **kwargs
        )

    with (
        patch.object(UserTemplateHandler, "serialize_applications", serialize_spy),
        patch.object(CoreHandler, "import_applications_to_workspace", import_spy),
    ):
        user_template_handler = UserTemplateHandler()
        content = user_template_handler.serialize_template_content(revision)
        with transaction.atomic():
            installed = user_template_handler.install_template_content(
                installer, target, revision, content
            )

    assert len(configs) == 2
    for config in configs:
        assert config.is_user_template is True
        assert config.is_duplicate is False
        assert config.exclude_sensitive_data is True
        assert config.include_permission_data is False

    integrations = list(
        LocalBaserowIntegration.objects.filter(
            application__in=[app.id for app in installed]
        )
    )
    assert integrations
    for integration in integrations:
        assert integration.authorized_subject_type == UserSubjectType.type
        assert integration.authorized_subject_id == installer.id

    database = next(app for app in installed if app.get_type().type == "database")
    table = database.specific.table_set.get()
    installed_file_field = table.field_set.get(name="File")
    files = [
        value
        for value in table.get_model()
        .objects.values_list(installed_file_field.db_column, flat=True)
        .order_by("id")
        if value
    ]
    assert len(files) == 1
    installed_name = files[0][0]["name"]
    assert not installed_name.startswith("tpl")
    assert files[0][0]["visible_name"] == "notes.txt"
    # The file of the copy is stored and served like any other one.
    assert UserFileHandler().get_user_file_by_name(installed_name)
