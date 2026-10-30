from unittest.mock import patch

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

import pytest
from freezegun import freeze_time

from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import IsNotAdminError
from baserow.core.handler import CoreHandler
from baserow.core.models import Template
from baserow.core.user_templates.actions import (
    ApproveUserTemplateAdminActionType,
    RejectUserTemplateAdminActionType,
)
from baserow.core.user_templates.constants import UserTemplateState
from baserow.core.user_templates.exceptions import (
    TemplateAlreadyApproved,
    TemplateAlreadyRejected,
    TemplateBlocked,
    TemplateHasNoContent,
    TemplateNotReviewable,
    TemplateRejectReasonRequired,
    TemplateUpdated,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from tests.baserow.core.user_templates.utils import create_template


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

    root = revision = create_template(data_fixture, data_fixture.create_user())
    for index, revision_state in enumerate(revision_states):
        if index:
            revision = data_fixture.create_user_template_revision(root)
        data_fixture.set_user_template_state(root, revision_state, revision)
    return root, revision


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,revision_states,unlisted",
    [
        ("approve", ["in_review"], None),
        ("approve", ["rejected"], None),
        ("approve", ["rejected", "private"], None),
        # The edit of a listed template replaces it in the listing.
        ("approve", ["public", "in_review"], None),
        ("reject", ["public"], True),
        ("reject", ["in_review"], False),
        ("reject", ["public", "rejected"], True),
        # Only the edit is rejected, the approved revision stays listed.
        ("reject", ["public", "in_review"], False),
    ],
)
def test_review(data_fixture, action, revision_states, unlisted):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, revision_states)
    submitted_on = Template.objects.get(id=latest.id).submitted_on
    listed_before = list(CoreHandler().list_templates(admin, listed=True))

    with patch("baserow.core.action.signals.action_done.send") as action_done:
        review(action, admin, root, latest.id)

    latest = Template.objects.with_review_state().get(id=latest.id)
    assert latest.reviewed_by == admin and latest.reviewed_on is not None
    listed = list(CoreHandler().list_templates(admin, listed=True))
    if action == "approve":
        assert latest.review_state == Template.ReviewState.APPROVED
        # Kept when the template was submitted, otherwise it's now.
        assert latest.submitted_on == (submitted_on or latest.submitted_on) is not None
        assert latest.get_root().public_revision_id == latest.id
        assert listed == [latest]
        # The rejection is closed: making it public again won't need a review.
        assert latest.review_open_rejection is False
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
    assert [
        (call.kwargs["action_type"].type, call.kwargs["action_params"])
        for call in action_done.call_args_list
    ] == [(f"admin_{action}_user_template", params)]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,revision_states,case,error",
    [
        ("approve", ["private"], "latest", TemplateNotReviewable),
        ("approve", ["public"], "latest", TemplateNotReviewable),
        ("approve", ["withdrawn_rejected"], "latest", TemplateNotReviewable),
        ("reject", ["private"], "latest", TemplateNotReviewable),
        ("reject", ["rejected"], "latest", TemplateNotReviewable),
        ("approve", ["blocked", "in_review"], "latest", TemplateBlocked),
        ("reject", ["public_blocked"], "latest", TemplateBlocked),
        ("approve", ["in_review", "pruned"], "latest", TemplateHasNoContent),
        ("approve", ["in_review"], "not_staff", IsNotAdminError),
        ("reject", ["public"], "not_staff", IsNotAdminError),
        ("approve", ["rejected", "private"], "previous", TemplateUpdated),
        ("reject", ["public", "private"], "previous", TemplateUpdated),
        ("approve", ["in_review"], "other", TemplateUpdated),
        # Reviewed by another admin, or changed, since the admin saw it.
        ("approve", ["public"], "seen_in_review", TemplateAlreadyApproved),
        ("reject", ["rejected"], "seen_in_review", TemplateAlreadyRejected),
        ("reject", ["private"], "seen_public", TemplateUpdated),
        # Taken out of the listing by another admin, while staying rejected.
        ("approve", ["rejected"], "seen_listed", TemplateAlreadyRejected),
    ],
)
def test_refused_review(data_fixture, action, revision_states, case, error):
    admin = data_fixture.create_user(is_staff=case != "not_staff")
    states = [state for state in revision_states if state != "pruned"]
    root, latest = create_reviewable(data_fixture, states)
    if "pruned" in revision_states:
        Template.objects.filter(id=latest.id).update(pruned_at=timezone.now())
    revision_id = {
        "previous": root.id,
        "other": create_template(data_fixture, admin).id,
    }.get(case, latest.id)
    seen_state = {
        "seen_in_review": UserTemplateState.IN_REVIEW,
        "seen_public": UserTemplateState.PUBLIC,
    }.get(case)
    seen_listed = True if case == "seen_listed" else None
    before = list(Template.objects.values().order_by("id"))

    with (
        patch("baserow.core.action.signals.action_done.send") as action_done,
        pytest.raises(error),
    ):
        review(action, admin, root, revision_id, seen_state, seen_listed)

    assert list(Template.objects.values().order_by("id")) == before
    assert not action_done.called


@pytest.mark.django_db
def test_reject_needs_a_reason(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, ["public"])
    before = list(Template.objects.values().order_by("id"))

    with pytest.raises(TemplateRejectReasonRequired):
        UserTemplateHandler().reject_template(
            admin, root.id, latest.id, "   ", UserTemplateState.PUBLIC, True
        )

    assert list(Template.objects.values().order_by("id")) == before


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
        if query["sql"].startswith("SELECT") and 'FROM "core_template"' in query["sql"]
    ]
    assert selects[0].endswith("FOR UPDATE")


@pytest.mark.django_db
def test_approve_waiting_revisions(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    waiting = {
        name: create_reviewable(data_fixture, states)
        for name, states in [
            ("never_listed", ["in_review"]),
            ("listed_edit", ["public", "in_review"]),
            ("resubmitted", ["rejected", "in_review"]),
            ("blocked", ["blocked", "in_review"]),
            ("marked", ["marked", "in_review"]),
            ("no_content", ["in_review"]),
            ("private", ["private"]),
        ]
    }
    Template.objects.filter(id=waiting["no_content"][1].id).update(
        pruned_at=timezone.now()
    )
    before = {name: get_state(root) for name, (root, _) in waiting.items()}

    with freeze_time("2026-10-30 12:00"):
        approved = UserTemplateHandler().approve_waiting_revisions(admin)

    # Approved like one by one, as `test_review` tests.
    assert approved == 3
    for name in ["never_listed", "listed_edit", "resubmitted"]:
        root, revision = waiting[name]
        revision.refresh_from_db()
        assert Template.objects.get(id=root.id).public_revision_id == revision.id
        assert revision.review_state == Template.ReviewState.APPROVED
        assert revision.reviewed_by == admin
        assert revision.reviewed_on.isoformat() == "2026-10-30T12:00:00+00:00"
        assert get_state(root) == UserTemplateState.PUBLIC
    for name in ["blocked", "marked", "no_content", "private"]:
        assert get_state(waiting[name][0]) == before[name]


@pytest.mark.django_db
def test_approve_waiting_locks_roots_in_id_order(data_fixture):
    admin = data_fixture.create_user(is_staff=True)

    def approve(count):
        # The revisions in review are created in the reverse order of their roots.
        roots = [create_template(data_fixture, admin) for _ in range(count)]
        for root in reversed(roots):
            revision = data_fixture.create_user_template_revision(root)
            data_fixture.set_user_template_state(root, "in_review", revision)
        with transaction.atomic(), CaptureQueriesContext(connection) as queries:
            UserTemplateHandler().approve_waiting_revisions(admin)
        return [query["sql"] for query in queries.captured_queries]

    queries = approve(2)

    # In as many queries however many templates wait.
    assert len(approve(5)) == len(queries)
    locks = [query for query in queries if query.endswith("FOR UPDATE")]
    assert len(locks) == 1
    # Selects only the ids, so it orders by its first column.
    assert locks[0].startswith('SELECT "core_template"."id" AS "id" FROM')
    assert locks[0].endswith("ORDER BY 1 ASC FOR UPDATE")


@pytest.mark.parametrize("unlisted", [None, False, True])
def test_reject_description(unlisted):
    params = dict(template_id=1, template_name="Name", revision_id=2, reason="No")
    if unlisted is not None:
        params["unlisted"] = unlisted

    text = RejectUserTemplateAdminActionType.get_long_description(params)

    taken_out = " and taken out of the listing" if unlisted else ""
    assert text == f'Template "Name" (1) rejected with revision 2{taken_out}: "No"'
