from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.models import Template
from baserow.core.user_templates.actions import (
    UpdateUserTemplateVisibilityActionType,
)
from baserow.core.user_templates.exceptions import TemplateBlocked
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
    revision_ids,
)


def approval_off(data_fixture):
    return data_fixture.update_settings(user_templates_require_approval=False)


def create_revision(data_fixture, user, root, base_revision=None):
    return UserTemplateHandler().create_template_revision(
        user=user,
        root=root,
        base_revision=base_revision or root,
        name="Next",
        description="",
        icon=ICON,
        category_ids=[data_fixture.create_template_category().id],
        workspace=root.workspace,
    )


@pytest.mark.django_db
def test_submit_revision_lists_and_approves(data_fixture):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    latest = data_fixture.create_user_template_revision(root, workspace=root.workspace)

    make_public(user, root)

    root.refresh_from_db()
    latest.refresh_from_db()
    assert root.public_revision_id == latest.id
    assert latest.review_state == Template.ReviewState.APPROVED
    assert latest.submitted_on is not None and latest.reviewed_on is not None
    assert latest.reviewed_by is None
    root.full_clean(exclude=["open_application"])

    make_private(user, root)
    root.refresh_from_db()
    assert root.public_revision_id is None
    assert Template.objects.get(id=latest.id).review_state == "approved"

    make_public(user, root)
    assert Template.objects.get(id=root.id).public_revision_id == latest.id


@pytest.mark.django_db
def test_update_scheduled_while_public_isnt_listed_once_made_private(data_fixture):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = create_template(data_fixture, user, "public")
    make_private(user, root)

    create_revision(data_fixture, user, root)

    assert Template.objects.get(id=root.id).public_revision_id is None


def change_outcome(root, before):
    if list(Template.objects.values().order_by("id")) == before:
        return "unchanged"
    before = {row["id"]: row for row in before}
    root = Template.objects.get(id=root.id)
    latest = UserTemplateHandler().get_latest_revision(root)
    revisions = list(Template.objects.filter_by_root(id=root.id))
    pending = Template.ReviewState.PENDING
    assert [r.id for r in revisions if r.review_state == pending] in ([], [latest.id])
    for revision in revisions:
        old = before.get(revision.id)
        if revision.id != latest.id:
            withdrawn = {pending: Template.ReviewState.WITHDRAWN}
            allowed = {old["review_state"], withdrawn.get(old["review_state"])}
            assert revision.review_state in allowed
    reasons = {revision.id: revision.reject_reason for revision in revisions}
    kept_reasons = {
        id: before[id]["reject_reason"] if id in before else "" for id in reasons
    }
    listed_before = before[root.id]["public_revision_id"]
    if latest.review_state == Template.ReviewState.PENDING:
        assert latest.submitted_on is not None
        assert root.public_revision_id == listed_before
        assert reasons == kept_reasons
        return "review"
    if root.public_revision_id == latest.id != listed_before:
        assert latest.review_state == Template.ReviewState.APPROVED
        assert set(reasons.values()) == {""}
        return "listed"
    assert root.public_revision_id == listed_before
    assert reasons == kept_reasons
    return "draft"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "require_approval", [False, True], ids=["approval_off", "approval_on"]
)
@pytest.mark.parametrize("action", ["make_public", "update"])
@pytest.mark.parametrize(
    "revision_states,make_public_does,update_does",
    user_template_plan_rows(
        "1",
        [
            (["private"], ("listed", "review"), ("draft", "draft")),
            (["shared"], ("listed", "review"), ("draft", "draft")),
            (["in_review"], ("unchanged", "unchanged"), ("review", "review")),
            (["resubmitted"], ("unchanged", "unchanged"), ("review", "review")),
            (
                ["private", "in_review"],
                ("unchanged", "unchanged"),
                ("review", "review"),
            ),
            (["rejected"], ("review", "review"), ("draft", "draft")),
            (["rejected", "private"], ("review", "review"), ("draft", "draft")),
            (["withdrawn_rejected"], ("review", "review"), ("draft", "draft")),
            (["public"], ("unchanged", "unchanged"), ("listed", "review")),
            (["public", "private"], ("listed", "review"), ("listed", "review")),
            (["rejected", "public"], ("unchanged", "unchanged"), ("listed", "review")),
            (["public", "in_review"], ("unchanged", "unchanged"), ("listed", "review")),
            (["public", "rejected"], ("review", "review"), ("review", "review")),
            (
                ["public", "resubmitted"],
                ("unchanged", "unchanged"),
                ("review", "review"),
            ),
            (["blocked"], ("refused", "refused"), ("draft", "draft")),
            (["public_blocked"], ("refused", "refused"), ("draft", "draft")),
            (["rejected", "blocked"], ("refused", "refused"), ("draft", "draft")),
            (
                ["blocked", "in_review"],
                ("refused", "refused"),
                ("review", "review"),
            ),
        ],
    ),
)
def test_owner_is_told_whether_a_change_goes_to_review(
    data_fixture,
    require_approval,
    action,
    revision_states,
    make_public_does,
    update_does,
):
    data_fixture.update_settings(user_templates_require_approval=require_approval)
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    data_fixture.set_user_template_revision_states(root, revision_states)
    handler = UserTemplateHandler()
    latest = handler.get_latest_revision(Template.objects.get(id=root.id))
    annotated = Template.objects.with_template_state().get(id=latest.id)
    told = {
        getattr(handler, f"{action}_needs_review")(row, require_approval)
        for row in [latest, annotated]
    }
    before = list(Template.objects.values().order_by("id"))

    expected = {"make_public": make_public_does, "update": update_does}
    outcome = expected[action][require_approval]
    if outcome == "refused":
        with pytest.raises(TemplateBlocked):
            make_public(user, root)
    elif action == "make_public":
        make_public(user, root)
    else:
        create_revision(data_fixture, user, root, base_revision=latest)

    changed = change_outcome(root, before)
    assert changed == ("unchanged" if outcome == "refused" else outcome)
    blocked = Template.objects.get(id=root.id).blocked_at is not None
    assert told == {outcome == "review" and not blocked}
    if action == "make_public":
        assert handler.make_public_submits(latest) is (changed != "unchanged")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,unlisted,withdrawn,recorded",
    user_template_plan_rows(
        "2",
        [
            (["private"], None, None, None),
            (["public"], 0, None, 0),
            (["public", "private"], 0, None, 0),
            (["rejected", "public"], 1, None, 1),
            (["in_review"], None, 0, 0),
            (["rejected"], None, 0, 0),
            (["rejected", "private"], None, 0, 0),
            (["withdrawn_rejected"], None, None, None),
            (["public", "in_review"], 0, 1, 0),
            (["public", "rejected"], 0, 1, 0),
        ],
    ),
)
def test_make_private_withdraws_from_review(
    data_fixture, revision_states, unlisted, withdrawn, recorded
):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    data_fixture.set_user_template_revision_states(root, revision_states)
    revisions = revision_ids(root)

    def review_states():
        return [Template.objects.get(id=id).review_state for id in revisions]

    listed_before = Template.objects.get(id=root.id).public_revision_id
    expected = [
        Template.ReviewState.WITHDRAWN if index == withdrawn else state
        for index, state in enumerate(review_states())
    ]

    with recorded_actions() as actions:
        make_private(user, root)

    assert listed_before == (None if unlisted is None else revisions[unlisted])
    assert Template.objects.get(id=root.id).public_revision_id is None
    assert review_states() == expected
    assert [params["revision_id"] for _, params in actions] == (
        [] if recorded is None else [revisions[recorded]]
    )


@pytest.mark.django_db
@pytest.mark.parametrize("caller", ["make_public", "edit_of_listed"])
def test_approval_is_read_from_the_locked_settings_row(data_fixture, caller):
    user = data_fixture.create_user()
    root = create_template(
        data_fixture, user, "public" if caller == "edit_of_listed" else "private"
    )

    with stale_cached_settings(user_templates_require_approval=False):
        assert CoreHandler().get_settings().user_templates_require_approval is True
        with CaptureQueriesContext(connection) as queries:
            if caller == "make_public":
                latest = make_public(user, root)
            else:
                latest = create_revision(data_fixture, user, root)

    assert Template.objects.get(id=root.id).public_revision_id == latest.id
    sql = [query["sql"] for query in queries.captured_queries]
    settings_lock = next(
        i for i, q in enumerate(sql) if "core_settings" in q and "FOR SHARE" in q
    )
    root_lock = next(
        i for i, q in enumerate(sql) if "core_template" in q and "FOR UPDATE" in q
    )
    assert settings_lock < root_lock


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state,made_public", [("private", "public"), ("rejected", "in_review")]
)
def test_make_visibility_actions_registered(data_fixture, state, made_public):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = create_template(data_fixture, user, state, name="Mine")

    with recorded_actions() as actions:
        for action in [make_public, make_public, make_private, make_private]:
            action(user, root)

    # Repeating a change records nothing.
    params = {"template_id": root.id, "template_name": "Mine", "revision_id": root.id}
    assert actions == [
        (
            UpdateUserTemplateVisibilityActionType.type,
            {
                **params,
                "make_public": True,
                "public_listing_consent": True,
                "state": made_public,
            },
        ),
        (
            UpdateUserTemplateVisibilityActionType.type,
            {
                **params,
                "make_public": False,
                "public_listing_consent": False,
                "state": "private",
            },
        ),
    ]
    made_public_text = "sent to review" if made_public == "in_review" else "made public"
    assert [
        UpdateUserTemplateVisibilityActionType.get_long_description(params)
        for _, params in actions
    ] == [
        f'Template "Mine" ({root.id}) {made_public_text} with revision {root.id}, '
        "with the consent of the author to list it and their name",
        f'Template "Mine" ({root.id}) made private',
    ]


def test_old_visibility_audit_entry_is_described_as_made_public():
    params = {
        "template_id": 1,
        "template_name": "T",
        "revision_id": 1,
        "listed": True,
        "public_listing_consent": True,
    }

    assert UpdateUserTemplateVisibilityActionType.get_long_description(params) == (
        'Template "T" (1) made public with revision 1, with the consent of the '
        "author to list it and their name"
    )
