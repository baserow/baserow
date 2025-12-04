from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_405_METHOD_NOT_ALLOWED,
)

from baserow.api.errors import ERROR_USER_NOT_IN_GROUP


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


@pytest.mark.django_db
def test_read_team(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    sales = enterprise_data_fixture.create_team(name="Sales", workspace=workspace)

    response = api_client.get(
        reverse(
            "api:enterprise:teams:item",
            kwargs={"team_id": sales.id},
        ),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == sales.id
    assert response_json["name"] == sales.name


@pytest.mark.django_db
def test_list_teams(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    sales = enterprise_data_fixture.create_team(name="Sales", workspace=workspace)
    engineering = enterprise_data_fixture.create_team(
        name="Engineering", workspace=workspace
    )

    response = api_client.get(
        reverse("api:enterprise:teams:list", kwargs={"workspace_id": workspace.id}),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == sales.id
    assert response_json[0]["name"] == sales.name
    assert response_json[1]["id"] == engineering.id
    assert response_json[1]["name"] == engineering.name


@pytest.mark.django_db
def test_list_search_teams(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    sales = enterprise_data_fixture.create_team(name="Sales", workspace=workspace)
    enterprise_data_fixture.create_team(name="Engineering", workspace=workspace)

    response = api_client.get(
        f"{reverse('api:enterprise:teams:list', kwargs={'workspace_id': workspace.id})}?search=Sal",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert response_json[0]["id"] == sales.id
    assert response_json[0]["name"] == sales.name


@pytest.mark.django_db
def test_create_team(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:enterprise:teams:list", kwargs={"workspace_id": workspace.id}),
        {"name": "Executives"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "Executives"
    assert response_json["workspace"] == workspace.id


@pytest.mark.django_db
def test_put_team(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    sales = enterprise_data_fixture.create_team(name="Sales", workspace=workspace)

    response = api_client.put(
        reverse("api:enterprise:teams:item", kwargs={"team_id": sales.id}),
        {"name": "Engineering"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == sales.id
    assert response_json["name"] == "Engineering"


@pytest.mark.django_db
def test_put_team_not_as_workspace_member(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace()
    sales = enterprise_data_fixture.create_team(name="Sales", workspace=workspace)

    response = api_client.put(
        reverse("api:enterprise:teams:item", kwargs={"team_id": sales.id}),
        {"name": "Engineering"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == ERROR_USER_NOT_IN_GROUP


@pytest.mark.django_db
def test_delete_team(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    response = api_client.delete(
        reverse("api:enterprise:teams:item", kwargs={"team_id": team.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_team_not_as_workspace_member(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace()
    team = enterprise_data_fixture.create_team(workspace=workspace)

    response = api_client.delete(
        reverse("api:enterprise:teams:item", kwargs={"team_id": team.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == ERROR_USER_NOT_IN_GROUP


@pytest.mark.django_db
def test_read_team_subject(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject = enterprise_data_fixture.create_subject(team=team)

    response = api_client.get(
        reverse(
            "api:enterprise:teams:subject-detail",
            kwargs={"team_id": team.id, "subject_id": subject.id},
        ),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["team"] == team.id
    assert response_json["id"] == subject.id


@pytest.mark.django_db
def test_list_team_subjects(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject1 = enterprise_data_fixture.create_subject(team=team)
    subject2 = enterprise_data_fixture.create_subject(team=team)

    response = api_client.get(
        reverse(
            "api:enterprise:teams:subject-list",
            kwargs={"team_id": team.id},
        ),
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == subject1.id
    assert response_json[1]["id"] == subject2.id


@pytest.mark.django_db
def test_create_team_subject_by_id(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    response = api_client.post(
        reverse("api:enterprise:teams:subject-list", kwargs={"team_id": team.id}),
        {"subject_id": user.id, "subject_type": "auth.User"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["team"] == team.id
    assert response_json["subject_id"] == user.id
    assert response_json["subject_type"] == "auth.User"


@pytest.mark.django_db
def test_create_team_subject_by_email(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    response = api_client.post(
        reverse("api:enterprise:teams:subject-list", kwargs={"team_id": team.id}),
        {"subject_user_email": user.email, "subject_type": "auth.User"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["team"] == team.id
    assert response_json["subject_id"] == user.id
    assert response_json["subject_type"] == "auth.User"


@pytest.mark.django_db
def test_patch_team_subject(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject = enterprise_data_fixture.create_subject(team=team)

    response = api_client.patch(
        reverse(
            "api:enterprise:teams:subject-detail",
            kwargs={"team_id": team.id, "subject_id": subject.id},
        ),
        {"subject_id": 123},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_delete_team_subject(api_client, data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(workspace=workspace)
    subject = enterprise_data_fixture.create_subject(team=team)

    response = api_client.delete(
        reverse(
            "api:enterprise:teams:subject-detail",
            kwargs={"team_id": team.id, "subject_id": subject.id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
