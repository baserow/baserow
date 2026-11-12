from django.urls import reverse

import pytest

from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.service import IdentityService
from baserow.core.models import User, UserProfile, WorkspaceUser
from baserow.core.trash.handler import TrashHandler


@pytest.mark.django_db
@pytest.mark.parametrize(
    "feature_flags, expected_status",
    [([], 403), (["agents"], 403), (["identities"], 200), (["*"], 200)],
    ids=["disabled", "legacy-flag", "identities-flag", "wildcard"],
)
def test_identity_creation_requires_current_feature_flag(
    data_fixture, api_client, settings, feature_flags, expected_status
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    managers = (
        User.objects_and_identities,
        UserProfile.objects,
        WorkspaceUser.objects_and_identities,
    )
    counts_before = [manager.count() for manager in managers]
    settings.FEATURE_FLAGS = feature_flags

    response = api_client.post(
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id}),
        {"name": "Worker"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == expected_status
    if expected_status == 403:
        assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
        assert [manager.count() for manager in managers] == counts_before
    else:
        identity = IdentityHandler().get_identity(response.json()["id"])
        assert IdentityHandler.get_workspace(identity) == workspace
        assert identity.profile.user_type == UserProfile.UserType.IDENTITY
        assert [manager.count() for manager in managers] == [
            count + 1 for count in counts_before
        ]


@pytest.mark.django_db
def test_existing_identities_stay_protected_when_creation_is_disabled(
    data_fixture, api_client, settings
):
    owner, owner_token = data_fixture.create_user_and_token()
    _, outsider_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=owner)
    identity = data_fixture.create_identity(workspace=workspace, name="Existing")
    list_url = reverse(
        "api:identities:workspace", kwargs={"workspace_id": workspace.id}
    )
    item_url = reverse("api:identities:item", kwargs={"identity_id": identity.id})
    owner_headers = {"HTTP_AUTHORIZATION": f"JWT {owner_token}"}
    outsider_headers = {"HTTP_AUTHORIZATION": f"JWT {outsider_token}"}
    settings.FEATURE_FLAGS = []

    response = api_client.get(list_url, **owner_headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == [identity.id]
    response = api_client.get(list_url, **outsider_headers)
    assert response.status_code == 401
    assert response.json()["error"] == "PERMISSION_DENIED"
    for response in [
        api_client.patch(
            item_url, {"name": "Forbidden"}, format="json", **outsider_headers
        ),
        api_client.delete(item_url, **outsider_headers),
    ]:
        assert response.status_code == 400
        assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    identity.refresh_from_db()
    assert identity.first_name == "Existing"
    assert not identity.profile.trashed

    response = api_client.patch(
        item_url, {"name": "Updated"}, format="json", **owner_headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert api_client.delete(item_url, **owner_headers).status_code == 204
    assert api_client.get(list_url, **owner_headers).json()["count"] == 0
    response = api_client.patch(
        reverse("api:trash:restore"),
        {"trash_item_type": "identity", "trash_item_id": identity.profile.id},
        format="json",
        **owner_headers,
    )
    assert response.status_code == 204
    response = api_client.get(list_url, **owner_headers)
    assert [(item["id"], item["name"]) for item in response.json()["results"]] == [
        (identity.id, "Updated")
    ]
    response = api_client.post(
        list_url, {"name": "New"}, format="json", **owner_headers
    )
    assert response.status_code == 403
    assert response.json()["error"] == "ERROR_FEATURE_DISABLED"
    assert IdentityHandler().get_queryset(workspace).count() == 1


@pytest.mark.django_db
def test_admin_can_crud_search_and_soft_delete_identities(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    url = reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.post(
        url, {"name": "Writer", "role_uid": "MEMBER"}, format="json", **headers
    )
    assert response.status_code == 200
    identity_id = response.json()["id"]
    assert response.json()["last_active"] is None
    assert response.json()["user_type"] == "identity"

    api_client.post(url, {"name": "Other"}, format="json", **headers)
    response = api_client.get(f"{url}?search=Writer&sorts=%2Bname", **headers)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["name"] == "Writer"

    item_url = reverse("api:identities:item", kwargs={"identity_id": identity_id})
    response = api_client.patch(
        item_url, {"name": "Writer 2"}, format="json", **headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Writer 2"

    assert api_client.delete(item_url, **headers).status_code == 204
    assert User.objects_and_identities.filter(
        id=identity_id, profile__trashed=True
    ).exists()
    assert not IdentityHandler().get_queryset(workspace).filter(id=identity_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("sorts", [None, "+name", "-name"])
def test_identity_pagination_with_duplicate_names(data_fixture, api_client, sorts):
    """Tied names must have stable ordering across page boundaries."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    identities = [
        data_fixture.create_identity(workspace=workspace, name=f"Identity {i % 3}")
        for i in range(400)
    ]
    expected = sorted(identities, key=lambda identity: identity.id)
    if sorts:
        expected.sort(
            key=lambda identity: identity.first_name, reverse=sorts == "-name"
        )

    url = reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id})
    result_ids = []
    for page in range(1, 5):
        params = {"page": page, "size": 100}
        if sorts:
            params["sorts"] = sorts
        response = api_client.get(url, params, HTTP_AUTHORIZATION=f"JWT {token}")
        assert response.status_code == 200
        assert response.json()["count"] == 400
        result_ids.extend(identity["id"] for identity in response.json()["results"])

    assert result_ids == [identity.id for identity in expected]
    assert len(set(result_ids)) == 400


@pytest.mark.django_db
def test_list_identities_page_size_is_limited(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    url = reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.get(f"{url}?size=201", **headers)
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_PAGE_SIZE_LIMIT"

    response = api_client.get(f"{url}?size=200", **headers)
    assert response.status_code == 200


@pytest.mark.django_db
def test_member_can_list_but_cannot_mutate_identities(data_fixture, api_client):
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    member, token = data_fixture.create_user_and_token()
    WorkspaceUser.objects.create(
        user=member, workspace=workspace, permissions="MEMBER", order=0
    )
    data_fixture.create_identity(workspace=workspace, name="Visible")
    url = reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    assert api_client.get(url, **headers).status_code == 200
    assert (
        api_client.post(url, {"name": "Denied"}, format="json", **headers).status_code
        == 401
    )


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_nonmember_identity_mutations_return_user_not_in_workspace(
    data_fixture, api_client, method
):
    """All Identity mutations expose the standard workspace-membership API error."""

    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    identity = data_fixture.create_identity(workspace=workspace, name="Writer")
    _, token = data_fixture.create_user_and_token()
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    workspace_url = reverse(
        "api:identities:workspace", kwargs={"workspace_id": workspace.id}
    )
    identity_url = reverse("api:identities:item", kwargs={"identity_id": identity.id})

    if method == "post":
        response = api_client.post(
            workspace_url, {"name": "Denied"}, format="json", **headers
        )
    elif method == "patch":
        response = api_client.patch(
            identity_url, {"name": "Denied"}, format="json", **headers
        )
    else:
        response = api_client.delete(identity_url, **headers)

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert list(
        IdentityHandler().get_queryset(workspace).values_list("first_name", flat=True)
    ) == ["Writer"]


def test_identity_list_openapi_schema_matches_paginated_response(api_client):
    """The published list contract includes pagination, filters, and team summaries."""

    schema = api_client.get(reverse("api:json_schema")).json()
    operation = schema["paths"]["/api/identities/workspace/{workspace_id}/"]["get"]
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "workspace_id",
        "page",
        "size",
        "search",
        "sorts",
    }

    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    components = schema["components"]["schemas"]
    pagination = components[response_schema["$ref"].split("/")[-1]]
    assert set(pagination["properties"]) == {
        "count",
        "next",
        "previous",
        "results",
    }

    identity_ref = pagination["properties"]["results"]["items"]["$ref"]
    identity_schema = components[identity_ref.split("/")[-1]]
    teams_schema = identity_schema["properties"]["teams"]
    assert teams_schema["type"] == "array"
    team_ref = teams_schema["items"]["$ref"]
    assert set(components[team_ref.split("/")[-1]]["properties"]) == {"id", "name"}


def test_identity_openapi_operations_have_stable_ids_and_explicit_path_parameters(
    api_client,
):
    """Identity client operations have stable names and typed path parameters."""

    schema = api_client.get(reverse("api:json_schema")).json()
    operations = [
        (
            "/api/identities/workspace/{workspace_id}/",
            "get",
            "list_workspace_identities",
            "workspace_id",
        ),
        (
            "/api/identities/workspace/{workspace_id}/",
            "post",
            "create_workspace_identity",
            "workspace_id",
        ),
        ("/api/identities/{identity_id}/", "patch", "update_identity", "identity_id"),
        ("/api/identities/{identity_id}/", "delete", "delete_identity", "identity_id"),
    ]

    for path, method, operation_id, parameter_name in operations:
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        path_parameters = [
            parameter
            for parameter in operation["parameters"]
            if parameter["in"] == "path"
        ]
        assert len(path_parameters) == 1
        assert path_parameters[0]["name"] == parameter_name
        assert path_parameters[0]["schema"]["type"] == "integer"


@pytest.mark.django_db
def test_duplicate_identity_names_and_model_defaults(data_fixture):
    workspace = data_fixture.create_workspace()
    first = data_fixture.create_identity(workspace=workspace, name="Same")
    second = data_fixture.create_identity(workspace=workspace, name="Same")

    assert IdentityHandler.get_role_uid(first) == "MEMBER"
    assert first.profile.last_active is None
    assert first.id != second.id


@pytest.mark.django_db
def test_admin_can_restore_identity(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    identity = data_fixture.create_identity(workspace=workspace, name="Writer")

    IdentityService().delete_identity(user, identity)
    restored_profile = TrashHandler.restore_item(user, "identity", identity.profile.id)

    assert restored_profile.user_id == identity.id
    assert UserProfile.objects.filter(user=identity, trashed=False).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("length,status", [(150, 200), (151, 400)])
def test_identity_names_accept_up_to_150_characters(
    api_client, data_fixture, length, status
):
    """Identity users test plan 13.2.1."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:identities:workspace", kwargs={"workspace_id": workspace.id}),
        {"name": "A" * length},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == status
