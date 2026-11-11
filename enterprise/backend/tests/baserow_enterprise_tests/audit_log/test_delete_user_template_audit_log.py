from django.db import transaction

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import RootActionScopeType
from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.models import Template
from baserow.core.user_templates.actions import DeleteUserTemplateActionType
from baserow_enterprise.audit_log.models import AuditLogEntry

pytestmark = pytest.mark.django_db


def delete_template(user, template):
    with transaction.atomic():
        action_type_registry.get_by_type(DeleteUserTemplateActionType).do(
            user, template.id
        )


@pytest.mark.parametrize("as_staff", [False, True])
def test_delete_user_template_is_audit_logged(enterprise_data_fixture, as_staff):
    owner = enterprise_data_fixture.create_user(email="owner@example.com")
    staff = enterprise_data_fixture.create_user(is_staff=True)
    template = enterprise_data_fixture.create_user_template(user=owner, name="Mine")
    # The name of the latest revision is the one people know.
    enterprise_data_fixture.create_user_template_revision(template, name="Mine v2")

    delete_template(staff if as_staff else owner, template)

    entry = AuditLogEntry.objects.get(action_type=DeleteUserTemplateActionType.type)
    assert entry.user_id == (staff if as_staff else owner).id
    assert entry.workspace_id is None
    assert entry.action_params == {
        "template_id": template.id,
        "template_name": "Mine v2",
        "owner_id": owner.id,
        "owner_email": "owner@example.com",
    }
    assert entry.type == "Delete template"
    assert entry.description == f'Template "Mine v2" ({template.id}) deleted'


def test_delete_user_template_cannot_be_undone(enterprise_data_fixture):
    session_id = "session-id"
    owner = enterprise_data_fixture.create_user(session_id=session_id)
    template = enterprise_data_fixture.create_user_template(user=owner)

    delete_template(owner, template)

    assert not Action.objects.filter(type=DeleteUserTemplateActionType.type).exists()
    assert ActionHandler.undo(owner, [RootActionScopeType.value()], session_id) == []
    assert Template.objects.get(id=template.id).marked_for_deletion_at is not None


def test_delete_user_template_twice_is_audit_logged_once(enterprise_data_fixture):
    owner = enterprise_data_fixture.create_user()
    template = enterprise_data_fixture.create_user_template(user=owner)

    delete_template(owner, template)
    with pytest.raises(TemplateDoesNotExist):
        delete_template(owner, template)

    assert (
        AuditLogEntry.objects.filter(
            action_type=DeleteUserTemplateActionType.type
        ).count()
        == 1
    )
