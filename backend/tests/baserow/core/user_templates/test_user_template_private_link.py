from django.utils import timezone

import pytest

from baserow.core.action.registries import action_type_registry
from baserow.core.context import private_link_token
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.models import Template
from baserow.core.user_templates.actions import (
    RotateUserTemplatePrivateLinkActionType,
    UpdateUserTemplatePrivateLinkActionType,
)
from tests.baserow.core.user_templates.utils import (
    create_template,
    request_download,
    request_install,
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
    after = Template.objects.get(id=root.id)
    assert (after.slug, after.public_revision_id) == (root.slug, None)


def test_blocked_template_refuses_link_holder(data_fixture):
    owner, holder = data_fixture.create_user(), data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=holder)
    root = create_template(data_fixture, owner, state="shared")
    token = root.private_link_token
    Template.objects.filter(id=root.id).update(blocked_at=timezone.now())
    root = Template.objects.get(id=root.id)

    assert not opens_for(holder, root, token)
    with private_link_token(token):
        with pytest.raises(TemplateDoesNotExist):
            request_install(holder, workspace, root)
        with pytest.raises(TemplateDoesNotExist):
            request_download(holder, root)
