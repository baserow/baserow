from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time

from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import IsNotAdminError, TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.models import Template, UserTemplateState
from baserow.core.user_templates.actions import (
    ApproveUserTemplateAdminActionType,
    RejectUserTemplateAdminActionType,
)
from baserow.core.user_templates.exceptions import (
    TemplateAlreadyApproved,
    TemplateAlreadyRejected,
    TemplateBlocked,
    TemplateHasNoContent,
    TemplateNotReviewable,
    TemplateUpdated,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.test_utils.helpers import (
    stale_cached_settings,
    user_template_plan_rows,
)
from tests.baserow.core.user_templates.utils import (
    ICON,
    create_template,
    recorded_actions,
)


def get_state(root):
    latest = UserTemplateHandler().get_latest_revision(Template.objects.get(id=root.id))
    return UserTemplateHandler().get_template_state(latest)[0]


def review(action, admin, root, revision_id, seen_state=None, seen_listed=None):
    """
    Reviews the template in the state and listing it's in, unless `seen_state` or
    `seen_listed` is given.
    """

    seen_state = seen_state or get_state(root)
    if seen_listed is None:
        seen_listed = Template.objects.get(id=root.id).public_revision_id is not None
    if action == "approve":
        return action_type_registry.get_by_type(ApproveUserTemplateAdminActionType).do(
            admin, root.id, revision_id, seen_state, seen_listed
        )
    return action_type_registry.get_by_type(RejectUserTemplateAdminActionType).do(
        admin, root.id, revision_id, "Off topic", seen_state, seen_listed
    )


def create_reviewable(data_fixture, revision_states):
    """A user template whose revisions are in the states, and its latest one."""

    root = create_template(data_fixture, data_fixture.create_user())
    return root, data_fixture.set_user_template_revision_states(root, revision_states)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,revision_states,unlisted",
    [
        # Approved directly, without being made public again.
        ("approve", ["rejected"], None),
        ("reject", ["public"], True),
        ("reject", ["in_review"], False),
    ],
)
def test_review(data_fixture, action, revision_states, unlisted):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, revision_states)
    submitted_on = Template.objects.get(id=latest.id).submitted_on
    listed_before = list(CoreHandler().list_templates(admin, listed=True))

    with recorded_actions() as actions:
        review(action, admin, root, latest.id)

    latest = Template.objects.with_template_state().get(id=latest.id)
    assert latest.reviewed_by == admin and latest.reviewed_on is not None
    listed = list(CoreHandler().list_templates(admin, listed=True))
    if action == "approve":
        assert latest.review_state == Template.ReviewState.APPROVED
        assert latest.submitted_on == submitted_on is not None
        assert latest.get_root().public_revision_id == latest.id
        assert listed == [latest]
        # The rejection is closed: making it public again won't need a review.
        assert latest.has_open_rejection is False
    else:
        assert latest.review_state == Template.ReviewState.REJECTED
        assert listed == ([] if unlisted else listed_before)
    params = {
        "template_id": root.id,
        "template_name": latest.name,
        "revision_id": latest.id,
        "owner_id": root.owner_id,
    }
    if action == "reject":
        params.update(reason="Off topic", unlisted=unlisted)
        taken_out = " and taken out of the listing" if unlisted else ""
        assert RejectUserTemplateAdminActionType.get_long_description(params) == (
            f'Template "{latest.name}" ({root.id}) rejected with revision '
            f'{latest.id}{taken_out}: "Off topic"'
        )
    assert actions == [(f"admin_{action}_user_template", params)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,case,action,error",
    user_template_plan_rows(
        "6",
        [
            (["private"], "latest", "approve", TemplateNotReviewable),
            (["private"], "latest", "reject", TemplateNotReviewable),
            (["rejected"], "latest", "reject", TemplateNotReviewable),
            (["blocked", "in_review"], "latest", "approve", TemplateBlocked),
            (["in_review", "pruned"], "latest", "approve", TemplateHasNoContent),
            (["in_review"], "not_staff", "approve", IsNotAdminError),
            # The author's edit since the rejection isn't submitted.
            (["rejected", "private"], "previous", "approve", TemplateUpdated),
            # Not the revision of its row on the admin page.
            (["rejected", "private"], "latest", "approve", TemplateUpdated),
            # Deleted by its owner while the admin reviews it.
            (["marked", "in_review"], "latest", "approve", TemplateDoesNotExist),
            # Reviewed by another admin, or changed, since the admin saw it.
            (["public"], "seen_in_review", "approve", TemplateAlreadyApproved),
            (["rejected"], "seen_in_review", "reject", TemplateAlreadyRejected),
            (["private"], "seen_public", "reject", TemplateUpdated),
            # Taken out of the listing by another admin, while staying rejected.
            (["rejected"], "seen_listed", "approve", TemplateAlreadyRejected),
        ],
        key_columns=3,
    ),
)
def test_refused_review(data_fixture, action, revision_states, case, error):
    admin = data_fixture.create_user(is_staff=case != "not_staff")
    root, latest = create_reviewable(data_fixture, revision_states)
    revision_id = root.id if case == "previous" else latest.id
    seen_state = {
        "seen_in_review": UserTemplateState.IN_REVIEW,
        "seen_public": UserTemplateState.PUBLIC,
    }.get(case)
    seen_listed = True if case == "seen_listed" else None
    before = list(Template.objects.values().order_by("id"))

    with recorded_actions() as actions, pytest.raises(error):
        review(action, admin, root, revision_id, seen_state, seen_listed)

    assert list(Template.objects.values().order_by("id")) == before
    assert actions == []


@pytest.mark.django_db
def test_review_locks_the_root(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, ["in_review"])

    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        UserTemplateHandler().approve_template(
            admin, root.id, latest.id, UserTemplateState.IN_REVIEW, False
        )

    selects = [
        query["sql"]
        for query in queries.captured_queries
        if 'FROM "core_template"' in query["sql"]
    ]
    # Locked by its first read, so nothing is read before the lock.
    assert "FOR UPDATE" in selects[0]


def changes(root, before):
    """
    What changed of the revisions of a user template since `before`, by the
    index of each revision, with the ids of revisions as indexes too, so that two
    templates in the same states compare.

    :param root: The template.
    :param before: The rows of its revisions before, oldest first.
    :return: The changed fields of each revision.
    """

    ids = [row["id"] for row in before]
    after = Template.objects.filter_by_root(id=root.id).order_by("version").values()
    as_index = {"public_revision_id": lambda id: id if id is None else ids.index(id)}
    return [
        {
            key: as_index.get(key, lambda value: value)(value)
            for key, value in row.items()
            if old[key] != value
        }
        for old, row in zip(before, after)
    ]


def revision_rows(root):
    return list(
        Template.objects.filter_by_root(id=root.id).order_by("version").values()
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,approved",
    user_template_plan_rows(
        "5",
        [
            # Whether switching approval off approves the template like an admin.
            (["in_review"], True),
            (["public", "in_review"], True),
            (["rejected", "public", "in_review"], True),
            (["private", "in_review"], True),
            # Rejected since it was last approved, so an admin reviews it.
            (["rejected", "in_review"], False),
            (["resubmitted"], False),
            (["public", "resubmitted"], False),
            # Not approved: no content, blocked, marked for deletion, or nothing in
            # review.
            (["in_review", "pruned"], False),
            (["blocked", "in_review"], False),
            (["marked", "in_review"], False),
            (["private"], False),
            (["public"], False),
            (["rejected"], False),
            (["public", "rejected"], False),
            (["rejected", "private"], False),
            (["withdrawn_rejected"], False),
        ],
    ),
)
def test_switching_approval_off_approves_like_an_admin(
    data_fixture, revision_states, approved
):
    admin = data_fixture.create_user(is_staff=True)
    switched, reviewed = [
        create_reviewable(data_fixture, revision_states)[0] for _ in range(2)
    ]
    before = {root.id: revision_rows(root) for root in [switched, reviewed]}
    queued = Template.objects.review_queue().filter_by_root(id=reviewed.id).first()

    with freeze_time("2026-10-30 12:00"):
        if approved:
            review("approve", admin, reviewed, queued.id)
        reviewed_changes = changes(reviewed, before[reviewed.id])
        CoreHandler().update_settings(admin, user_templates_require_approval=False)

    switched_changes = changes(switched, before[switched.id])
    assert switched_changes == reviewed_changes
    assert any(switched_changes) is approved
    if approved:
        assert get_state(switched) == UserTemplateState.PUBLIC


@pytest.mark.django_db
@pytest.mark.parametrize(
    "stored,change,approved",
    [
        (True, {"user_templates_require_approval": False}, True),
        # The cached settings can be stale: only switching the stored setting
        # off approves the templates in review.
        (False, {"user_templates_require_approval": False}, False),
        (True, {"user_templates_require_approval": True}, False),
        (True, {"allow_new_signups": False}, False),
    ],
)
def test_switching_approval_off_approves_the_pending_templates(
    data_fixture, stored, change, approved
):
    admin = data_fixture.create_user(is_staff=True)
    pending = [create_reviewable(data_fixture, ["in_review"])[0] for _ in range(2)]

    with (
        stale_cached_settings(user_templates_require_approval=stored),
        CaptureQueriesContext(connection) as queries,
    ):
        CoreHandler().update_settings(admin, **change)

    expected = UserTemplateState.PUBLIC if approved else UserTemplateState.IN_REVIEW
    assert [get_state(root) for root in pending] == [expected, expected]
    if not approved:
        return
    # Read under a row lock, so a concurrent switch waits for this one.
    sql = [query["sql"] for query in queries.captured_queries]
    read = next(
        i for i, q in enumerate(sql) if "core_settings" in q and "FOR UPDATE" in q
    )
    update = next(
        i for i, q in enumerate(sql) if q.startswith('UPDATE "core_settings"')
    )
    # The settings row is updated before any template is locked, so a concurrent
    # submit either sees approval off or is approved here.
    first_lock = next(
        i
        for i, q in enumerate(sql)
        if 'FROM "core_template"' in q and "FOR UPDATE" in q
    )
    assert read < update < first_lock


@pytest.mark.django_db
def test_approve_refused_after_the_review_moved_to_a_new_revision(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    root, seen = create_reviewable(data_fixture, ["in_review"])
    # The owner updates it while the admin looks at the revision in review.
    new = UserTemplateHandler().create_template_revision(
        user=root.owner,
        root=root,
        base_revision=seen,
        name="Edit",
        description="",
        icon=ICON,
        category_ids=[data_fixture.create_template_category().id],
        workspace=root.workspace,
    )

    with pytest.raises(TemplateUpdated), transaction.atomic():
        UserTemplateHandler().approve_template(
            admin, root.id, seen.id, UserTemplateState.IN_REVIEW, False
        )

    assert Template.objects.get(id=new.id).review_state == "pending"
    assert Template.objects.get(id=root.id).public_revision_id is None
