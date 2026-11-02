import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.models import Template
from baserow.core.user_templates.actions import (
    RotateUserTemplatePrivateLinkActionType,
    UpdateUserTemplatePrivateLinkActionType,
)

pytestmark = pytest.mark.django_db


def update_private_link(user, template, enabled):
    return action_type_registry.get_by_type(UpdateUserTemplatePrivateLinkActionType).do(
        user, template.id, enabled
    )


def rotate_private_link(user, template):
    return action_type_registry.get_by_type(RotateUserTemplatePrivateLinkActionType).do(
        user, template.id
    )


def opens_for(user, template, token):
    return (
        Template.objects.openable(user, private_link_token=token).filter_by_root(
            id=template.id
        )
    ).exists()


@pytest.mark.parametrize("operation", ["rotate", "remove"])
def test_rotate_and_remove_revoke_old_link(data_fixture, operation):
    owner, holder = data_fixture.create_user(), data_fixture.create_user()
    root = data_fixture.create_user_template(user=owner)
    update_private_link(owner, root, True)
    old_token = Template.objects.get(id=root.id).private_link_token
    assert opens_for(holder, root, old_token)

    if operation == "rotate":
        rotate_private_link(owner, root)
    else:
        update_private_link(owner, root, False)

    assert not opens_for(holder, root, old_token)
    new_token = Template.objects.get(id=root.id).private_link_token
    if operation == "rotate":
        assert opens_for(holder, root, new_token)
    # The template keeps its link and visibility.
    after = Template.objects.get(id=root.id)
    assert (after.slug, after.public_revision_id) == (root.slug, None)
