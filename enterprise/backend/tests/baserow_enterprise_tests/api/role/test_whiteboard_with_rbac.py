from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
)

from baserow.contrib.whiteboard.operations import (
    ReadWhiteboardOperationType,
    UpdateWhiteboardContentOperationType,
)
from baserow_enterprise.role.constants import (
    BUILDER_ROLE_UID,
    COMMENTER_ROLE_UID,
    EDITOR_ROLE_UID,
    VIEWER_ROLE_UID,
)
from baserow_enterprise.role.default_roles import default_roles
from baserow_enterprise.role.handler import RoleAssignmentHandler


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def test_read_whiteboard_op_is_in_viewer_role():
    """
    Regression: forgetting to add a custom application operation to
    `default_roles.py` makes the enterprise RBAC permission manager reject
    the operation for every role, even ADMIN. This guard fails fast if
    that registration is dropped.
    """

    assert ReadWhiteboardOperationType in default_roles[VIEWER_ROLE_UID]


def test_update_whiteboard_content_op_is_in_editor_role():
    # `EDITOR` is the lowest tier that can edit a whiteboard scene; the
    # `BUILDER` and `ADMIN` lists are populated by extending `EDITOR`,
    # so they automatically gain the same operation. `VIEWER` and
    # `COMMENTER` stay strictly read-only.
    assert UpdateWhiteboardContentOperationType in default_roles[EDITOR_ROLE_UID]
    assert UpdateWhiteboardContentOperationType in default_roles[BUILDER_ROLE_UID]
    assert UpdateWhiteboardContentOperationType not in default_roles[COMMENTER_ROLE_UID]
    assert UpdateWhiteboardContentOperationType not in default_roles[VIEWER_ROLE_UID]


@pytest.mark.django_db(transaction=True)
def test_viewer_role_can_read_whiteboard_via_api(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    whiteboard.content = {"elements": [{"id": "abc"}]}
    whiteboard.save()

    role = RoleAssignmentHandler().get_role_by_uid(VIEWER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    response = api_client.get(
        reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"content": {"elements": [{"id": "abc"}]}}


@pytest.mark.django_db(transaction=True)
def test_viewer_role_cannot_update_whiteboard_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    role = RoleAssignmentHandler().get_role_by_uid(VIEWER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    response = api_client.put(
        reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id}),
        {"content": {"elements": [{"id": "x"}]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
def test_editor_role_can_update_whiteboard_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    role = RoleAssignmentHandler().get_role_by_uid(EDITOR_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    response = api_client.put(
        reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id}),
        {"content": {"elements": [{"id": "x"}]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db(transaction=True)
def test_commenter_role_cannot_update_whiteboard_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    role = RoleAssignmentHandler().get_role_by_uid(COMMENTER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    response = api_client.put(
        reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id}),
        {"content": {"elements": [{"id": "x"}]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
def test_builder_role_can_update_whiteboard_content(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    role = RoleAssignmentHandler().get_role_by_uid(BUILDER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    response = api_client.put(
        reverse("api:whiteboard:item", kwargs={"whiteboard_id": whiteboard.id}),
        {"content": {"elements": [{"id": "x"}]}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db(transaction=True)
def test_builder_role_can_broadcast_changes(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)

    role = RoleAssignmentHandler().get_role_by_uid(BUILDER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    response = api_client.post(
        reverse(
            "api:whiteboard:broadcast_changes",
            kwargs={"whiteboard_id": whiteboard.id},
        ),
        {"payload": {"type": "scene_update", "elements": []}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
