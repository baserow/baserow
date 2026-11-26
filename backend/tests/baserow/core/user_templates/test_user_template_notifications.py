from django.contrib.auth import get_user_model

import pytest

from baserow.core.handler import CoreHandler
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.core.user_templates.notification_types import (
    BlockedUserTemplateChangedNotificationType,
    UserTemplateApprovedNotificationType,
    UserTemplateBlockedNotificationType,
    UserTemplateChangeRejectedNotificationType,
    UserTemplateInReviewNotificationType,
    UserTemplateRejectedNotificationType,
    UserTemplateUnblockedNotificationType,
    UserTemplateUnlistedNotificationType,
    mark_admin_notifications_read,
)
from tests.baserow.core.user_templates.utils import (
    block,
    create_template,
    latest_id,
    make_private,
    make_public,
    notified,
    review,
    unblock,
    update_details,
)

User = get_user_model()


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

    expected = {
        "template_id": root.id,
        "template_name": notified_name,
        "author_name": owner.first_name,
    }
    assert notified(UserTemplateInReviewNotificationType) == (
        [(admin.id, expected)] if notified_name else []
    )


@pytest.mark.django_db(transaction=True)
def test_blocked_template_change_notifies_blocking_admin_once_while_unread(
    data_fixture,
):
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
            data__template_name="First",
            notificationrecipient__recipient=admin,
        ),
    )
    update_details(owner, root, name="Third")

    assert notified(BlockedUserTemplateChangedNotificationType) == [
        (
            admin.id,
            {
                "template_id": template_id,
                "template_name": name,
                "author_name": author.first_name,
            },
        )
        for template_id, name, author in [
            (other_root.id, "Other", owner),
            (admins_own_root.id, "Own", other_admin),
            (root.id, "First", owner),
            (root.id, "Third", owner),
        ]
    ]


def leave(user, **fields):
    for field, value in fields.items():
        setattr(user, field, value)
    user.save()


ADMIN_STEPS = {
    "public": lambda anna, ben, maya, root: make_public(maya, root),
    "private": lambda anna, ben, maya, root: make_private(maya, root),
    "edit": lambda anna, ben, maya, root: update_details(maya, root),
    "anna approves": lambda anna, ben, maya, root: STEPS["approve"](anna, maya, root),
    "anna rejects": lambda anna, ben, maya, root: STEPS["reject"](anna, maya, root),
    "ben rejects": lambda anna, ben, maya, root: STEPS["reject"](ben, maya, root),
    "anna blocks": lambda anna, ben, maya, root: block(anna, root),
    "ben blocks": lambda anna, ben, maya, root: block(ben, root, reason="Scam"),
    "anna unblocks": lambda anna, ben, maya, root: unblock(anna, root),
    "approval off": lambda anna, ben, maya, root: STEPS["approval off"](
        anna, maya, root
    ),
    "anna inactive": lambda anna, ben, maya, root: leave(anna, is_active=False),
    "anna not staff": lambda anna, ben, maya, root: leave(anna, is_staff=False),
    "anna deleted": lambda anna, ben, maya, root: anna.delete(),
    "carl admin": lambda anna, ben, maya, root: User.objects.filter(
        first_name="carl"
    ).update(is_staff=True),
}
IN_REVIEW = UserTemplateInReviewNotificationType.type
CHANGED = BlockedUserTemplateChangedNotificationType.type


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "steps,expected",
    [
        ("public", [("anna", IN_REVIEW, False), ("ben", IN_REVIEW, False)]),
        (
            "public,private,public",
            [("anna", IN_REVIEW, False), ("ben", IN_REVIEW, False)],
        ),
        (
            "public,anna rejects,public",
            [("anna", IN_REVIEW, True), ("ben", IN_REVIEW, True)]
            + [("anna", IN_REVIEW, False)],
        ),
        (
            "public,anna rejects,anna not staff,public",
            [("anna", IN_REVIEW, True), ("ben", IN_REVIEW, True)]
            + [("ben", IN_REVIEW, False)],
        ),
        ("public,anna approves", [("anna", IN_REVIEW, True), ("ben", IN_REVIEW, True)]),
        ("public,anna blocks", [("anna", IN_REVIEW, True), ("ben", IN_REVIEW, True)]),
        ("public,approval off", [("anna", IN_REVIEW, True), ("ben", IN_REVIEW, True)]),
        (
            "public,anna approves,edit,ben rejects,edit,anna approves,"
            "anna deleted,carl admin,edit",
            [("ben", IN_REVIEW, True), ("ben", IN_REVIEW, True)]
            + [("ben", IN_REVIEW, False), ("carl", IN_REVIEW, False)],
        ),
        ("anna blocks,edit,edit", [("anna", CHANGED, False)]),
        ("anna blocks,ben blocks,edit", [("ben", CHANGED, False)]),
        ("anna blocks,edit,ben blocks", [("anna", CHANGED, True)]),
        ("anna blocks,edit,anna unblocks", [("anna", CHANGED, True)]),
        ("anna blocks,anna inactive,edit", [("ben", CHANGED, False)]),
        ("anna blocks,anna deleted,edit", [("ben", CHANGED, False)]),
    ],
)
def test_admin_notifications_follow_decisions(data_fixture, steps, expected):
    anna = data_fixture.create_user(is_staff=True, first_name="anna")
    ben = data_fixture.create_user(is_staff=True, first_name="ben")
    maya = data_fixture.create_user()
    data_fixture.create_user(first_name="carl")
    root = create_template(data_fixture, maya)

    for step in steps.split(","):
        ADMIN_STEPS[step](anna, ben, maya, root)

    rows = NotificationRecipient.objects.filter(
        notification__type__in=[IN_REVIEW, CHANGED]
    ).values_list("recipient__first_name", "notification__type", "read")
    assert sorted(rows) == sorted(expected)


@pytest.mark.django_db
def test_admin_notifications_marked_read_in_two_queries(
    data_fixture, django_assert_num_queries
):
    data_fixture.create_user(is_staff=True)
    data_fixture.create_user(is_staff=True)
    owner = data_fixture.create_user()
    roots = [create_template(data_fixture, owner) for _ in range(3)]
    for root in roots:
        make_public(owner, root)

    with django_assert_num_queries(2):
        mark_admin_notifications_read([root.id for root in roots])

    assert not NotificationRecipient.objects.filter(read=False).exists()


APPROVED = UserTemplateApprovedNotificationType
REJECTED = UserTemplateRejectedNotificationType
CHANGE_REJECTED = UserTemplateChangeRejectedNotificationType
UNLISTED = UserTemplateUnlistedNotificationType
BLOCKED = UserTemplateBlockedNotificationType
UNBLOCKED = UserTemplateUnblockedNotificationType


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "own,steps,expected",
    [
        (False, f"{LISTED},edit,approve", (APPROVED, "Renamed", None)),
        (False, f"{LISTED},edit,approval off", (APPROVED, "Renamed", None)),
        (False, "public,reject", (REJECTED, "Recipes", "Off topic")),
        (False, f"{LISTED},edit,reject", (CHANGE_REJECTED, "Renamed", "Off topic")),
        (False, f"{LISTED},reject", (UNLISTED, "Recipes", "Off topic")),
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

    author_types = [APPROVED, REJECTED, CHANGE_REJECTED, UNLISTED, BLOCKED, UNBLOCKED]
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
