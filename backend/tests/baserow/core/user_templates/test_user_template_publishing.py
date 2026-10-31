from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.cache import invalidate_cached_settings, set_cached_settings
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.models import Template, Workspace
from baserow.core.user_templates.actions import (
    UpdateUserTemplateVisibilityActionType,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from tests.baserow.core.user_templates.utils import ICON, create_template, make_public


def make_private(user, template):
    return action_type_registry.get_by_type(UpdateUserTemplateVisibilityActionType).do(
        user, template.id, False, public_listing_consent=False
    )


def approval_off(data_fixture):
    return data_fixture.update_settings(user_templates_require_approval=False)


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
def test_make_public_opens_and_private_closes_access(data_fixture):
    approval_off(data_fixture)
    user, other = data_fixture.create_user(), data_fixture.create_user()
    root = create_template(data_fixture, user)

    def assert_access(expected):
        revision = Template.objects.get(id=root.id)
        for actor in [other, AnonymousUser()]:
            assert Template.objects.openable(actor).filter(id=root.id).exists() is (
                expected
            )
            workspace = Workspace.objects.get(id=root.workspace_id)
            assert workspace.has_openable_template(actor) is expected
        if expected:
            UserTemplateHandler().check_install_access(other, revision)
        else:
            with pytest.raises(TemplateDoesNotExist):
                UserTemplateHandler().check_install_access(other, revision)

    make_public(user, root)
    assert_access(True)
    make_private(user, root)
    assert_access(False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state,made_private_before_commit,listed",
    [
        ("public", False, "new"),
        ("private", False, None),
        ("public_blocked", False, "old"),
        # The update was scheduled while the template was public.
        ("public", True, None),
    ],
)
def test_update_relists_public_template(
    data_fixture, state, made_private_before_commit, listed
):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = data_fixture.set_user_template_state(
        create_template(data_fixture, user), state
    )
    if made_private_before_commit:
        make_private(user, root)

    revision = UserTemplateHandler().create_template_revision(
        user=user,
        root=root,
        base_revision=root,
        name="Next",
        description="",
        icon=ICON,
        category_ids=[data_fixture.create_template_category().id],
        workspace=root.workspace,
    )

    expected = {"new": revision.id, "old": root.id, None: None}[listed]
    assert Template.objects.get(id=root.id).public_revision_id == expected
    if listed == "new":
        assert Template.objects.get(id=revision.id).review_state == "approved"


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
@pytest.mark.parametrize("change", [None, "edit", "withdraw", "listed"])
def test_make_public_of_rejected_template_goes_to_review(data_fixture, change):
    # Even when approval isn't required.
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = rejected = create_template(data_fixture, user)
    if change == "listed":
        # An edit of a listed template, which stays listed meanwhile.
        data_fixture.set_user_template_state(root, "public")
        rejected = data_fixture.create_user_template_revision(root)
    data_fixture.set_user_template_state(root, "rejected", rejected)
    if change == "edit":
        create_revision(data_fixture, user, root)
    elif change == "withdraw":
        make_private(user, root)

    latest = make_public(user, root)
    submitted_on = Template.objects.get(id=latest.id).submitted_on
    make_public(user, root)

    latest = Template.objects.get(id=latest.id)
    assert latest.get_root().public_revision_id == (
        root.id if change == "listed" else None
    )
    assert latest.review_state == Template.ReviewState.PENDING
    assert latest.submitted_on == submitted_on is not None
    assert Template.objects.get(id=rejected.id).reject_reason == "Reason"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "revision_states,withdrawn",
    [
        (["in_review"], True),
        (["rejected"], True),
        (["rejected", "in_review"], True),
        (["rejected", "private"], True),
        (["withdrawn_rejected"], False),
        # Unlisted, and an edit of it is withdrawn from review too.
        (["public", "in_review"], True),
        (["public", "rejected"], True),
    ],
)
def test_make_private_withdraws_from_review(data_fixture, revision_states, withdrawn):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = revision = create_template(data_fixture, user)
    for index, revision_state in enumerate(revision_states):
        if index:
            revision = data_fixture.create_user_template_revision(root)
        data_fixture.set_user_template_state(root, revision_state, revision)
    expected = (
        Template.ReviewState.WITHDRAWN
        if withdrawn
        else Template.objects.get(id=revision.id).review_state
    )

    with patch("baserow.core.action.signals.action_done.send") as action_done:
        make_private(user, root)

    revision = Template.objects.get(id=revision.id)
    listed = revision_states[0] == "public"
    assert revision.review_state == expected
    # The listed revision is recorded, otherwise the withdrawn one.
    assert [
        call.kwargs["action_params"]["revision_id"]
        for call in action_done.call_args_list
    ] == ([root.id if listed else revision.id] if withdrawn else [])


@pytest.mark.django_db
# Also after it was approved, listed and made private. The edit of a listed
# template is tested by `test_newer_edit_withdraws_waiting_revision`.
@pytest.mark.parametrize("relist", [False, True])
def test_approval_sends_make_public_to_review(data_fixture, relist):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    if relist:
        data_fixture.set_user_template_state(root, "public")
        make_private(user, root)

    make_public(user, root)

    root = Template.objects.get(id=root.id)
    assert (root.review_state, root.public_revision_id) == ("pending", None)


@pytest.mark.django_db
@pytest.mark.parametrize("require_approval", [True, False])
def test_newer_edit_withdraws_waiting_revision(data_fixture, require_approval):
    data_fixture.update_settings(user_templates_require_approval=require_approval)
    user = data_fixture.create_user()
    root = data_fixture.set_user_template_state(
        create_template(data_fixture, user), "public"
    )
    waiting = data_fixture.create_user_template_revision(root)
    data_fixture.set_user_template_state(root, "in_review", waiting)

    latest = create_revision(data_fixture, user, root, base_revision=waiting)

    assert Template.objects.get(id=waiting.id).review_state == "withdrawn"
    latest = Template.objects.get(id=latest.id)
    assert latest.review_state == ("pending" if require_approval else "approved")
    assert latest.get_root().public_revision_id == (
        root.id if require_approval else latest.id
    )


@pytest.mark.django_db
@pytest.mark.parametrize("caller", ["make_public", "edit_of_listed"])
def test_approval_is_read_from_the_locked_settings_row(data_fixture, settings, caller):
    settings.BASEROW_CACHE_TTL_SECONDS = 600
    user = data_fixture.create_user()
    root = create_template(data_fixture, user)
    if caller == "edit_of_listed":
        data_fixture.set_user_template_state(root, "public")
    stale = approval_off(data_fixture)
    stale.user_templates_require_approval = True
    set_cached_settings(stale)
    assert CoreHandler().get_settings().user_templates_require_approval is True

    with CaptureQueriesContext(connection) as queries:
        if caller == "make_public":
            latest = make_public(user, root)
        else:
            latest = create_revision(data_fixture, user, root)
    invalidate_cached_settings()

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
@pytest.mark.parametrize("blocked", [False, True])
def test_edit_of_template_in_review_moves_the_review(data_fixture, blocked):
    user = data_fixture.create_user()
    root = data_fixture.set_user_template_state(
        create_template(data_fixture, user), "blocked" if blocked else "private"
    )
    data_fixture.set_user_template_state(root, "in_review")

    revision = create_revision(data_fixture, user, root)

    root = Template.objects.get(id=root.id)
    revision = Template.objects.get(id=revision.id)
    assert root.review_state == Template.ReviewState.WITHDRAWN
    assert revision.review_state == Template.ReviewState.PENDING
    assert revision.submitted_on is not None
    assert root.public_revision_id is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state,made_public", [("private", "public"), ("rejected", "in_review")]
)
def test_make_visibility_actions_registered(data_fixture, state, made_public):
    approval_off(data_fixture)
    user = data_fixture.create_user()
    root = data_fixture.set_user_template_state(
        create_template(data_fixture, user, name="Mine"), state
    )

    with patch("baserow.core.action.signals.action_done.send") as action_done:
        for action in [make_public, make_public, make_private, make_private]:
            action(user, root)

    # Repeating a change records nothing.
    params = {"template_id": root.id, "template_name": "Mine", "revision_id": root.id}
    assert [
        (call.kwargs["action_type"].type, call.kwargs["action_params"])
        for call in action_done.call_args_list
    ] == [
        (
            UpdateUserTemplateVisibilityActionType.type,
            {
                **params,
                "listed": True,
                "public_listing_consent": True,
                "state": made_public,
            },
        ),
        (
            UpdateUserTemplateVisibilityActionType.type,
            {
                **params,
                "listed": False,
                "public_listing_consent": False,
                "state": "private",
            },
        ),
    ]
    made_public_text = "sent to review" if made_public == "in_review" else "made public"
    assert [
        UpdateUserTemplateVisibilityActionType.get_long_description(
            call.kwargs["action_params"]
        )
        for call in action_done.call_args_list
    ] == [
        f'Template "Mine" ({root.id}) {made_public_text} with revision {root.id}, '
        "with the consent of the author to list it and their name",
        f'Template "Mine" ({root.id}) made private',
    ]


def test_visibility_action_description_renders_entries_without_state():
    # Entries recorded before templates could go to review have no state.
    params = {
        "template_id": 1,
        "template_name": "Mine",
        "revision_id": 2,
        "listed": True,
        "public_listing_consent": True,
    }

    assert UpdateUserTemplateVisibilityActionType.get_long_description(
        params
    ).startswith('Template "Mine" (1) made public with revision 2, with')
