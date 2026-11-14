import json

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
    BlockUserTemplateAdminActionType,
    RejectUserTemplateAdminActionType,
    UnblockUserTemplateAdminActionType,
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
    make_private,
    make_public,
    recorded_actions,
    template_row_writes,
)


def get_state(root):
    latest = UserTemplateHandler().get_latest_revision(Template.objects.get(id=root.id))
    return UserTemplateHandler().get_template_state(latest)[0]


CURRENT = object()


def review(
    action,
    admin,
    root,
    revision_id,
    seen_state=None,
    seen_listed=None,
    seen_reviewed_on=CURRENT,
):
    seen_state = seen_state or get_state(root)
    if seen_listed is None:
        seen_listed = Template.objects.get(id=root.id).public_revision_id is not None
    if seen_reviewed_on is CURRENT:
        seen_reviewed_on = Template.objects.get(id=revision_id).reviewed_on
    seen = (seen_state, seen_listed, seen_reviewed_on)
    if action == "approve":
        return action_type_registry.get_by_type(ApproveUserTemplateAdminActionType).do(
            admin, root.id, revision_id, *seen
        )
    return action_type_registry.get_by_type(RejectUserTemplateAdminActionType).do(
        admin, root.id, revision_id, "Off topic", *seen
    )


def create_reviewable(data_fixture, revision_states):
    root = create_template(data_fixture, data_fixture.create_user())
    return root, data_fixture.set_user_template_revision_states(root, revision_states)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,revision_states,unlisted,toggled_with_approval",
    [
        ("approve", ["rejected"], None, None),
        ("reject", ["public"], True, None),
        ("reject", ["in_review"], False, None),
        ("approve", ["in_review"], None, True),
        ("reject", ["public"], True, False),
    ],
)
def test_review(data_fixture, action, revision_states, unlisted, toggled_with_approval):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, revision_states)
    seen = (
        get_state(root),
        Template.objects.get(id=root.id).public_revision_id is not None,
        Template.objects.get(id=latest.id).reviewed_on,
    )
    if toggled_with_approval is not None:
        CoreHandler().update_settings(
            admin, user_templates_require_approval=toggled_with_approval
        )
        make_private(root.owner, root)
        make_public(root.owner, root)
    submitted_on = Template.objects.get(id=latest.id).submitted_on
    listed_before = list(CoreHandler().list_templates(admin, listed=True))

    with recorded_actions() as actions:
        review(action, admin, root, latest.id, *seen)

    latest = Template.objects.with_template_state().get(id=latest.id)
    assert latest.reviewed_by == admin and latest.reviewed_on is not None
    listed = list(CoreHandler().list_templates(admin, listed=True))
    if action == "approve":
        assert latest.review_state == Template.ReviewState.APPROVED
        assert latest.submitted_on == submitted_on is not None
        assert latest.get_root().public_revision_id == latest.id
        assert listed == [latest]
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
            (["rejected", "private"], "previous", "approve", TemplateUpdated),
            (["rejected", "private"], "latest", "approve", TemplateUpdated),
            (["marked", "in_review"], "latest", "approve", TemplateDoesNotExist),
            (["public"], "seen_in_review", "approve", TemplateAlreadyApproved),
            (["rejected"], "seen_in_review", "reject", TemplateAlreadyRejected),
            (["private"], "seen_public", "reject", TemplateUpdated),
            (["rejected"], "seen_listed", "approve", TemplateAlreadyRejected),
            (["resubmitted"], "seen_before_rejection", "approve", TemplateUpdated),
            (["resubmitted"], "seen_before_rejection", "reject", TemplateUpdated),
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
    seen_reviewed_on = None if case == "seen_before_rejection" else CURRENT
    before = list(Template.objects.values().order_by("id"))

    with recorded_actions() as actions, pytest.raises(error):
        review(
            action, admin, root, revision_id, seen_state, seen_listed, seen_reviewed_on
        )

    assert list(Template.objects.values().order_by("id")) == before
    assert actions == []


@pytest.mark.django_db
def test_review_locks_the_root(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, ["in_review"])

    with transaction.atomic(), CaptureQueriesContext(connection) as queries:
        UserTemplateHandler().approve_template(
            admin, root.id, latest.id, UserTemplateState.IN_REVIEW, False, None
        )

    selects = [
        query["sql"]
        for query in queries.captured_queries
        if 'FROM "core_template"' in query["sql"]
    ]
    assert "FOR UPDATE" in selects[0]


def changes(root, before):
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
            (["in_review"], True),
            (["public", "in_review"], True),
            (["rejected", "public", "in_review"], True),
            (["private", "in_review"], True),
            (["rejected", "in_review"], False),
            (["resubmitted"], False),
            (["public", "resubmitted"], False),
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
    sql = [query["sql"] for query in queries.captured_queries]
    read = next(
        i for i, q in enumerate(sql) if "core_settings" in q and "FOR UPDATE" in q
    )
    update = next(
        i for i, q in enumerate(sql) if q.startswith('UPDATE "core_settings"')
    )
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
            admin, root.id, seen.id, UserTemplateState.IN_REVIEW, False, None
        )

    assert Template.objects.get(id=new.id).review_state == "pending"
    assert Template.objects.get(id=root.id).public_revision_id is None


@pytest.mark.django_db
@pytest.mark.parametrize("revision_states", [["rejected"], ["rejected", "in_review"]])
@pytest.mark.parametrize("switched_off_while", ["in_review", "private"])
def test_approved_rejection_stays_closed(
    data_fixture, revision_states, switched_off_while
):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, revision_states)
    review("approve", admin, root, latest.id)
    make_private(root.owner, root)
    make_public(root.owner, root)
    assert get_state(root) == UserTemplateState.IN_REVIEW

    if switched_off_while == "private":
        make_private(root.owner, root)
    CoreHandler().update_settings(admin, user_templates_require_approval=False)
    if switched_off_while == "private":
        make_public(root.owner, root)

    assert get_state(root) == UserTemplateState.PUBLIC
    assert Template.objects.get(id=root.id).public_revision_id == latest.id


def rows_filtered_per_row(queryset):
    plan = json.loads(queryset.explain(analyze=True, format="json"))[0]["Plan"]
    nodes = [plan]
    filtered = 0
    while nodes:
        node = nodes.pop()
        if node["Actual Loops"] > 1:
            filtered += node["Actual Loops"] * sum(
                node.get(f"Rows Removed by {by}", 0)
                for by in ("Filter", "Index Recheck", "Join Filter")
            )
        nodes.extend(node.get("Plans", []))
    return filtered


@pytest.mark.django_db
def test_template_lists_read_only_the_later_revisions(data_fixture):
    """Pinned planner settings, so these few rows are planned like many."""

    owner = data_fixture.create_user()
    templates = 40
    for _ in range(templates):
        rejected = data_fixture.create_user_template(user=owner)
        data_fixture.set_user_template_state(rejected, "rejected")
        edited = data_fixture.create_user_template()
        data_fixture.set_user_template_revision_states(
            edited, ["public", "private", "private"]
        )
        blocked = data_fixture.create_user_template()
        data_fixture.set_user_template_state(blocked, "blocked")
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE core_template")
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("SET LOCAL max_parallel_workers_per_gather = 0")

    rejected_tab = UserTemplateHandler().list_templates_for_admin(
        UserTemplateState.REJECTED
    )
    blocked_tab = UserTemplateHandler().list_templates_for_admin(
        UserTemplateState.BLOCKED
    )
    owned = CoreHandler().list_templates(owner, owned=True)

    assert rows_filtered_per_row(rejected_tab) < templates // 4
    assert rows_filtered_per_row(blocked_tab) < templates // 4
    assert rows_filtered_per_row(owned) < templates // 4


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action,revision_states",
    [
        ("approve", ["rejected"]),
        ("approve", ["rejected", "in_review"]),
        ("approve", ["rejected", "resubmitted"]),
        ("reject", ["public"]),
        ("reject", ["public", "public"]),
    ],
)
def test_review_writes_each_template_row_once(data_fixture, action, revision_states):
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_reviewable(data_fixture, revision_states)

    with template_row_writes() as writes:
        review(action, admin, root, latest.id)

    assert writes and set(writes.values()) == {1}


def latest_id(root):
    return UserTemplateHandler().get_latest_revision(root).id


def block(admin, root, reason="Spam", revision_id=None):
    return action_type_registry.get_by_type(BlockUserTemplateAdminActionType).do(
        admin, root.id, revision_id or latest_id(root), reason
    )


def unblock(admin, root, revision_id=None):
    return action_type_registry.get_by_type(UnblockUserTemplateAdminActionType).do(
        admin, root.id, revision_id or latest_id(root)
    )


def create_blocked(data_fixture, admin, revision_states, changed):
    with freeze_time("2026-11-01 12:00"):
        root, latest = create_reviewable(data_fixture, revision_states)
        Template.objects.filter(id=latest.id).exclude(id=root.id).update(
            workspace=data_fixture.create_database_application().workspace
        )
        block(admin, root)
    if changed:
        workspace = data_fixture.create_workspace()
        data_fixture.create_database_application(workspace=workspace)
        with freeze_time("2026-11-01 12:01"):
            latest = UserTemplateHandler().create_template_revision(
                user=root.owner,
                root=root,
                base_revision=latest,
                name="Edited",
                description="",
                icon=ICON,
                category_ids=[data_fixture.create_template_category().id],
                workspace=workspace,
            )
    if changed == "reblocked":
        with freeze_time("2026-11-01 12:02"):
            block(admin, root, "Still spam")
    return root, latest


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,changed,approval_off,expected",
    [
        (["shared"], False, False, ("private", None, False, False)),
        (["shared"], True, False, ("private", None, False, False)),
        (["rejected"], False, False, ("rejected", None, False, True)),
        (["rejected"], True, False, ("rejected", None, False, True)),
        (["in_review"], False, False, ("in_review", None, True, False)),
        (["in_review"], True, False, ("in_review", None, True, False)),
        (["public"], False, False, ("public", "same", False, False)),
        (["public"], True, False, ("public", "latest", False, False)),
        (["public", "in_review"], False, False, ("public", "latest", False, False)),
        (["public", "in_review"], True, False, ("public", "latest", False, False)),
        (["public"], "reblocked", False, ("public", "latest", False, False)),
        (
            ["public", "in_review"],
            "reblocked",
            False,
            ("public", "latest", False, False),
        ),
        (["public", "rejected"], False, False, ("rejected", "same", False, True)),
        (["public", "rejected"], True, False, ("public", "latest", False, False)),
        (["in_review"], False, True, ("public", "latest", False, False)),
        (["rejected"], True, True, ("rejected", None, False, True)),
        (["resubmitted"], False, True, ("in_review", None, True, True)),
    ],
)
def test_unblock_restores_the_state_before_the_block(
    data_fixture, revision_states, changed, approval_off, expected
):
    state, listed, latest_pending, open_rejection = expected
    admin = data_fixture.create_user(is_staff=True)
    root, latest = create_blocked(data_fixture, admin, revision_states, changed)
    if approval_off:
        CoreHandler().update_settings(admin, user_templates_require_approval=False)
    block_fields = {"blocked_at", "blocked_by_id", "blocked_reason"}

    def snapshot():
        return [
            {key: value for key, value in row.items() if key not in block_fields}
            for row in Template.objects.values().order_by("id")
        ]

    before = snapshot()
    root_before = next(row for row in before if row["id"] == root.id)

    with recorded_actions() as unblocked:
        assert unblock(admin, root).id == latest.id

    root.refresh_from_db()
    listed_id = latest.id if listed == "latest" else None
    assert (root.blocked_at, root.blocked_by, root.blocked_reason) == (None, None, "")
    assert get_state(root) == state
    assert root.public_revision_id == (
        listed_id or (listed and root_before["public_revision_id"])
    )
    assert root.private_link_token == root_before["private_link_token"]
    pending = Template.objects.filter_by_root(id=root.id).filter(
        review_state=Template.ReviewState.PENDING
    )
    assert list(pending.values_list("id", flat=True)) == (
        [latest.id] if latest_pending else []
    )
    assert (
        Template.objects.with_template_state().get(id=root.id).has_open_rejection
        is open_rejection
    )
    if listed_id:
        listed_revision = Template.objects.get(id=listed_id)
        assert listed_revision.reviewed_by == admin
        assert listed_revision.submitted_on is not None
    else:
        assert snapshot() == before
    assert unblocked == [
        (
            "admin_unblock_user_template",
            {
                "template_id": root.id,
                "template_name": latest.name,
                "owner_id": root.owner_id,
                "state": state,
                "listed_revision_id": listed_id,
                "listed": bool(listed),
            },
        )
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,changed,approval_off",
    [
        (["shared"], False, False),
        (["public"], True, False),
        (["in_review"], False, True),
    ],
)
def test_unblock_writes_each_template_row_once(
    data_fixture, revision_states, changed, approval_off
):
    admin = data_fixture.create_user(is_staff=True)
    root, _ = create_blocked(data_fixture, admin, revision_states, changed)
    if approval_off:
        CoreHandler().update_settings(admin, user_templates_require_approval=False)

    with template_row_writes() as writes:
        unblock(admin, root)

    assert writes and set(writes.values()) == {1}


@pytest.mark.parametrize(
    "outcome,text",
    [
        ({}, "unblocked"),
        ({"state": "rejected", "listed_revision_id": None}, "unblocked, now rejected"),
        (
            {"state": "rejected", "listed_revision_id": None, "listed": True},
            "unblocked, listed, its edit now rejected",
        ),
        (
            {"state": "public", "listed_revision_id": None, "listed": True},
            "unblocked, now listed",
        ),
        (
            {"state": "public", "listed_revision_id": 5},
            "unblocked and listed with revision 5",
        ),
    ],
)
def test_unblock_audit_describes_the_state(outcome, text):
    params = {"template_id": 1, "template_name": "Old", "owner_id": 2, **outcome}

    assert (
        UnblockUserTemplateAdminActionType.get_long_description(params)
        == f'Template "Old" (1) {text}'
    )


@pytest.mark.django_db
def test_block_again_and_unblock_without_block(data_fixture):
    first_admin = data_fixture.create_user(is_staff=True)
    second_admin = data_fixture.create_user(is_staff=True)
    root, _ = create_reviewable(data_fixture, ["public"])
    listed, _ = create_reviewable(data_fixture, ["public"])

    with recorded_actions() as actions:
        with freeze_time("2026-11-01 12:00"):
            block(first_admin, root, "Spam")
        with freeze_time("2026-11-02 12:00"):
            block(second_admin, root, "Scam")
        before = list(Template.objects.values().order_by("id"))
        unblock(first_admin, listed)

    root.refresh_from_db()
    assert root.blocked_reason == "Scam"
    assert root.blocked_by == second_admin
    assert root.blocked_at.isoformat() == "2026-11-02T12:00:00+00:00"
    assert list(Template.objects.values().order_by("id")) == before
    assert get_state(listed) == UserTemplateState.PUBLIC
    params = {"template_id": root.id, "template_name": root.name}
    assert actions == [
        (
            "admin_block_user_template",
            {**params, "owner_id": root.owner_id, "reason": reason},
        )
        for reason in ["Spam", "Scam"]
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,seen,refused",
    [
        (["rejected", "private"], "previous", False),
        (["public"], "other", True),
    ],
)
def test_block_refuses_a_revision_of_another_template(
    data_fixture, revision_states, seen, refused
):
    admin = data_fixture.create_user(is_staff=True)
    root, _ = create_reviewable(data_fixture, revision_states)
    if seen == "other":
        revision_id = create_reviewable(data_fixture, ["public"])[1].id
    else:
        revision_id = root.id
    before = list(Template.objects.values().order_by("id"))

    if refused:
        with pytest.raises(TemplateUpdated):
            block(admin, root, revision_id=revision_id)
        assert list(Template.objects.values().order_by("id")) == before
    else:
        block(admin, root, revision_id=revision_id)
        assert get_state(root) == UserTemplateState.BLOCKED


@pytest.mark.django_db
def test_unblock_with_approval_off_leaves_other_templates_alone(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    other, _ = create_reviewable(data_fixture, ["in_review"])
    root, _ = create_reviewable(data_fixture, ["shared"])
    block(admin, other)
    block(admin, root)
    CoreHandler().update_settings(admin, user_templates_require_approval=False)

    unblock(admin, root)

    other.refresh_from_db()
    assert other.blocked_at is not None
    assert other.public_revision_id is None
