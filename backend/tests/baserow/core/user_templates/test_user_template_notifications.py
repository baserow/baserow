import pytest

from baserow.core.handler import CoreHandler
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import Notification
from baserow.core.user_templates.notification_types import (
    BlockedUserTemplateChangedNotificationType,
    UserTemplateApprovedNotificationType,
    UserTemplateBlockedNotificationType,
    UserTemplateInReviewNotificationType,
    UserTemplateRejectedNotificationType,
    UserTemplateUnblockedNotificationType,
)
from tests.baserow.core.user_templates.utils import (
    block,
    create_template,
    latest_id,
    make_public,
    notified,
    review,
    unblock,
    update_details,
)


def require_approval(required):
    return lambda admin, owner, root: CoreHandler().update_settings(
        admin, user_templates_require_approval=required
    )


STEPS = {
    "public": lambda admin, owner, root: make_public(owner, root),
    "edit": lambda admin, owner, root: update_details(owner, root),
    "approval off": require_approval(False),
    "approval on": require_approval(True),
    "approve": lambda admin, owner, root: review(
        "approve", admin, root, latest_id(root)
    ),
    "reject": lambda admin, owner, root: review("reject", admin, root, latest_id(root)),
    "block": lambda admin, owner, root: block(admin, root),
    "reblock": lambda admin, owner, root: block(admin, root, reason="Scam"),
    "unblock": lambda admin, owner, root: unblock(admin, root),
}
LISTED = "approval off,public,approval on"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "owner_is_admin,steps,notified_name",
    [
        (False, "public", "Recipes"),
        (True, "public", "Recipes"),
        (False, f"{LISTED},edit", "Renamed"),
        (False, f"{LISTED},edit,edit", None),
        (False, "public,reject,public", "Recipes"),
        (False, "public,reject,approval off,public", "Recipes"),
        (False, "public,block,unblock", None),
        (False, "approval off,public", None),
    ],
)
def test_in_review_notifies_admins(data_fixture, owner_is_admin, steps, notified_name):
    admin = data_fixture.create_user(is_staff=True)
    data_fixture.create_user(is_staff=True, is_active=False)
    data_fixture.create_user(is_staff=True, to_be_deleted=True)
    data_fixture.create_user()
    owner = data_fixture.create_user(is_staff=owner_is_admin)
    root = create_template(data_fixture, owner, name="Recipes")
    *setup, act = steps.split(",")
    for step in setup:
        STEPS[step](admin, owner, root)
    Notification.objects.all().delete()

    STEPS[act](admin, owner, root)

    expected = {"template_id": root.id, "template_name": notified_name}
    assert notified(UserTemplateInReviewNotificationType) == (
        [(admin.id, expected)] if notified_name else []
    )


@pytest.mark.django_db(transaction=True)
def test_blocked_template_change_notifies_each_admin_once_while_unread(data_fixture):
    admin = data_fixture.create_user(is_staff=True)
    other_admin = data_fixture.create_user(is_staff=True)
    owner = data_fixture.create_user()
    root = create_template(data_fixture, owner)
    other_root = create_template(data_fixture, owner)
    make_public(owner, root)
    block(admin, root)
    block(admin, other_root)
    update_details(owner, other_root, name="Other")
    update_details(owner, create_template(data_fixture, owner), name="Free")
    admins_own_root = create_template(data_fixture, other_admin)
    block(admin, admins_own_root)
    update_details(other_admin, admins_own_root, name="Own")

    update_details(owner, root, name="First")
    update_details(owner, root, name="Second")
    NotificationHandler.mark_notification_as_read(
        admin,
        Notification.objects.get(
            data={"template_id": root.id, "template_name": "First"},
            notificationrecipient__recipient=admin,
        ),
    )
    update_details(owner, root, name="Third")

    assert notified(BlockedUserTemplateChangedNotificationType) == [
        (admin.id, {"template_id": other_root.id, "template_name": "Other"}),
        (admin.id, {"template_id": admins_own_root.id, "template_name": "Own"}),
        (admin.id, {"template_id": root.id, "template_name": "First"}),
        (admin.id, {"template_id": root.id, "template_name": "Third"}),
        (other_admin.id, {"template_id": other_root.id, "template_name": "Other"}),
        (other_admin.id, {"template_id": root.id, "template_name": "First"}),
    ]


APPROVED = UserTemplateApprovedNotificationType
REJECTED = UserTemplateRejectedNotificationType
BLOCKED = UserTemplateBlockedNotificationType
UNBLOCKED = UserTemplateUnblockedNotificationType


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "own,steps,expected",
    [
        (False, f"{LISTED},edit,approve", (APPROVED, "Renamed", None)),
        (False, f"{LISTED},edit,approval off", (APPROVED, "Renamed", None)),
        (False, "public,reject", (REJECTED, "Recipes", "Off topic")),
        (False, "block", (BLOCKED, "Recipes", "Spam")),
        (False, "block,reblock", (BLOCKED, "Recipes", "Scam")),
        (False, "block,block", None),
        (False, "block,unblock", (UNBLOCKED, "Recipes", None)),
        (False, "unblock", None),
        (True, "public,approve", None),
        (True, "public,approval off", None),
    ],
)
def test_author_notified_of_moderation(data_fixture, own, steps, expected):
    owner = data_fixture.create_user(is_staff=own)
    admin = owner if own else data_fixture.create_user(is_staff=True)
    root = create_template(data_fixture, owner, name="Recipes")
    *setup, act = steps.split(",")
    for step in setup:
        STEPS[step](admin, owner, root)
    Notification.objects.all().delete()

    STEPS[act](admin, owner, root)

    author_types = [APPROVED, REJECTED, BLOCKED, UNBLOCKED]
    assert [(t, *n) for t in author_types for n in notified(t)] == (
        [
            (
                expected[0],
                owner.id,
                {"template_id": root.id, "template_name": expected[1]}
                | {"template_slug": root.slug}
                | ({"reason": expected[2]} if expected[2] else {}),
            )
        ]
        if expected
        else []
    )
