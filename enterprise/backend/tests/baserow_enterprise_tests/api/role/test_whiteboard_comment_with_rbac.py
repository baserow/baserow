from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
)

from baserow.contrib.whiteboard.comments.operations import (
    CreateWhiteboardCommentOperationType,
    DeleteWhiteboardCommentOperationType,
    ListWhiteboardCommentsOperationType,
    ResolveWhiteboardCommentOperationType,
    UpdateWhiteboardCommentOperationType,
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


def _doc(text="hi"):
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def test_list_op_in_commenter_role_not_viewer():
    # Comments are entirely hidden from VIEWERs (no list, no create) so
    # they don't see threads they can't participate in. Listing is the
    # commenter tier's responsibility, not the viewer tier's.
    assert ListWhiteboardCommentsOperationType not in default_roles[VIEWER_ROLE_UID]
    assert ListWhiteboardCommentsOperationType in default_roles[COMMENTER_ROLE_UID]
    assert ListWhiteboardCommentsOperationType in default_roles[EDITOR_ROLE_UID]
    assert ListWhiteboardCommentsOperationType in default_roles[BUILDER_ROLE_UID]


def test_mutate_ops_in_commenter_role_not_viewer():
    for op in (
        CreateWhiteboardCommentOperationType,
        UpdateWhiteboardCommentOperationType,
        DeleteWhiteboardCommentOperationType,
        ResolveWhiteboardCommentOperationType,
    ):
        assert op in default_roles[COMMENTER_ROLE_UID], op
        assert op in default_roles[EDITOR_ROLE_UID], op
        assert op in default_roles[BUILDER_ROLE_UID], op
        assert op not in default_roles[VIEWER_ROLE_UID], op


@pytest.mark.django_db(transaction=True)
def test_viewer_cannot_list_or_create(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    role = RoleAssignmentHandler().get_role_by_uid(VIEWER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    list_url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.get(list_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert resp.status_code == HTTP_401_UNAUTHORIZED

    resp = api_client.post(
        list_url,
        {"message": _doc(), "x": 0, "y": 0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db(transaction=True)
def test_commenter_can_create_and_resolve(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    role = RoleAssignmentHandler().get_role_by_uid(COMMENTER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        user, whiteboard.workspace, role=role, scope=whiteboard
    )

    list_url = reverse(
        "api:whiteboard:comments:list", kwargs={"whiteboard_id": whiteboard.id}
    )
    resp = api_client.post(
        list_url,
        {"message": _doc(), "x": 1.0, "y": 2.0},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp.status_code == HTTP_200_OK
    comment_id = resp.json()["id"]

    resolve_url = reverse(
        "api:whiteboard:comments:resolve", kwargs={"comment_id": comment_id}
    )
    resp = api_client.post(
        resolve_url,
        {"resolved": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert resp.status_code == HTTP_200_OK


@pytest.mark.django_db(transaction=True)
def test_commenter_can_delete_own_only(api_client, data_fixture):
    author, author_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=author)
    intruder, intruder_token = data_fixture.create_user_and_token()
    data_fixture.create_user_workspace(user=intruder, workspace=workspace)
    whiteboard = data_fixture.create_whiteboard_application(workspace=workspace)

    role = RoleAssignmentHandler().get_role_by_uid(COMMENTER_ROLE_UID)
    RoleAssignmentHandler().assign_role(
        intruder, whiteboard.workspace, role=role, scope=whiteboard
    )
    comment = data_fixture.create_whiteboard_comment(user=author, whiteboard=whiteboard)

    url = reverse("api:whiteboard:comments:item", kwargs={"comment_id": comment.id})
    resp = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {intruder_token}")
    assert resp.status_code == HTTP_401_UNAUTHORIZED

    resp = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {author_token}")
    assert resp.status_code == HTTP_204_NO_CONTENT
