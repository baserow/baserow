import os

from django.conf import settings
from django.db import transaction
from django.test import override_settings

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.actions import InstallTemplateActionType
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Template
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid

TEST_TEMPLATES_DIR = os.path.join(settings.BASE_DIR, "../../../tests/templates")


@pytest.mark.django_db
@pytest.mark.undo_redo
@override_settings(APPLICATION_TEMPLATES_DIR=TEST_TEMPLATES_DIR)
def test_can_undo_redo_install_template(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    handler = CoreHandler()
    handler.sync_templates()

    template = Template.objects.get(slug="example-template")

    installed_applications = action_type_registry.get_by_type(
        InstallTemplateActionType
    ).do(user, workspace, template)

    assert len(installed_applications) == 1
    assert Application.objects.get(pk=installed_applications[0].id) is not None

    undone_actions = ActionHandler.undo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(undone_actions, [InstallTemplateActionType])
    with pytest.raises(Application.DoesNotExist):
        Application.objects.get(pk=installed_applications[0].id)

    actions_redone = ActionHandler.redo(
        user, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(actions_redone, [InstallTemplateActionType])

    assert Application.objects.get(pk=installed_applications[0].id) is not None


@pytest.mark.import_export_workspace
@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
@pytest.mark.usefixtures("use_tmp_media_root")
def test_can_undo_redo_install_user_template(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    workspace = data_fixture.create_workspace(user=user)
    root = data_fixture.create_user_template(user=user)
    data_fixture.create_database_application(workspace=root.workspace, name="Mine")
    scopes = [WorkspaceActionScopeType.value(workspace_id=workspace.id)]

    with UserTemplateHandler().export_template_content(root) as resource:
        with transaction.atomic():
            installed_applications = action_type_registry.get_by_type(
                InstallTemplateActionType
            ).do(user, workspace, root, resource=resource)

    assert [app.name for app in installed_applications] == ["Mine"]
    assert Template.objects.get(id=root.id).install_count == 1

    # Undo and redo run in the transaction of the request.
    with transaction.atomic():
        undone_actions = ActionHandler.undo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(undone_actions, [InstallTemplateActionType])
    assert not Application.objects.filter(pk=installed_applications[0].id).exists()
    # An undone install still counts.
    assert Template.objects.get(id=root.id).install_count == 1

    with transaction.atomic():
        actions_redone = ActionHandler.redo(user, scopes, session_id)
    assert_undo_redo_actions_are_valid(actions_redone, [InstallTemplateActionType])
    assert Application.objects.filter(pk=installed_applications[0].id).exists()
    assert Template.objects.get(id=root.id).install_count == 1
