from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser

import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import TemplateDoesNotExist
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


@pytest.mark.django_db
def test_submit_revision_lists_and_approves(data_fixture):
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


@pytest.mark.django_db
def test_make_visibility_actions_registered(data_fixture):
    user = data_fixture.create_user()
    root = create_template(data_fixture, user, name="Mine")

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
            {**params, "listed": True, "public_listing_consent": True},
        ),
        (
            UpdateUserTemplateVisibilityActionType.type,
            {**params, "listed": False, "public_listing_consent": False},
        ),
    ]
    assert [
        UpdateUserTemplateVisibilityActionType.get_long_description(
            call.kwargs["action_params"]
        )
        for call in action_done.call_args_list
    ] == [
        f'Template "Mine" ({root.id}) made public with revision {root.id}, with '
        "the consent of the author to list it and their name",
        f'Template "Mine" ({root.id}) made private',
    ]
