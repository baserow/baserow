from django.core.cache import cache
from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from .utils import (
    GRAPH_REQUEST,
    MICROSOFT_SETTINGS,
    PERSONAL_TENANT_ID,
    FakeResponse,
    create_teams_integration,
)

GRAPH = "https://graph.microsoft.com/v1.0"
ACCOUNT_ID = "00000000-0000-0000-0000-00000000a11c"

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures("enterprise"),
]


@pytest.fixture
def enterprise(enterprise_data_fixture):
    cache.clear()
    with override_settings(DEBUG=True, **MICROSOFT_SETTINGS):
        enterprise_data_fixture.enable_enterprise()
        yield
    cache.clear()


def setup(data_fixture, **kwargs):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    integration = create_teams_integration(data_fixture, application=builder, **kwargs)
    return token, integration


def url(name, integration, **kwargs):
    return reverse(
        f"api:enterprise:microsoft_teams:{name}",
        kwargs={"integration_id": integration.id, **kwargs},
    )


def get(api_client, token, path):
    return api_client.get(path, HTTP_AUTHORIZATION=f"JWT {token}")


def test_list_teams(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture)
    request = mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(
            200,
            {
                "value": [
                    {"id": "t2", "displayName": "Sales"},
                    {"id": "t1", "displayName": "Marketing"},
                    {"displayName": "No id"},
                ]
            },
        ),
    )

    response = get(api_client, token, url("teams", integration))

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json() == [
        {"id": "t1", "name": "Marketing"},
        {"id": "t2", "name": "Sales"},
    ]
    assert request.call_args.kwargs["url"] == f"{GRAPH}/me/joinedTeams"


def test_list_channels_quotes_the_team_id(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture)
    request = mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(
            200,
            {
                "value": [
                    {
                        "id": "19:general@thread.tacv2",
                        "displayName": "General",
                        "membershipType": "standard",
                    }
                ]
            },
        ),
    )

    response = get(api_client, token, url("channels", integration, team_id="a:b@c"))

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json() == [
        {
            "id": "19:general@thread.tacv2",
            "name": "General",
            "membership_type": "standard",
        }
    ]
    assert request.call_args.kwargs["url"] == f"{GRAPH}/teams/a%3Ab%40c/channels"
    assert request.call_args.kwargs["params"] == {
        "$select": "id,displayName,membershipType"
    }


def test_a_dot_team_id_is_refused(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture)
    request = mocker.patch(GRAPH_REQUEST)

    response = get(api_client, token, url("channels", integration, team_id=".."))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MICROSOFT_TEAMS_PICKER"
    request.assert_not_called()


def test_list_chats_names_them(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture)
    request = mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(
            200,
            {
                "value": [
                    {"id": "c1", "topic": "Launch", "chatType": "group"},
                    {
                        "id": "c2",
                        "topic": None,
                        "chatType": "oneOnOne",
                        "members": [
                            {"userId": ACCOUNT_ID, "displayName": "Alice"},
                            {"userId": "bob", "displayName": "Bob"},
                        ],
                    },
                    {
                        "id": "c3",
                        "topic": None,
                        "chatType": "group",
                        "members": [
                            {"userId": "carol", "displayName": "Carol"},
                            {"userId": "dave", "email": "dave@contoso.com"},
                        ],
                    },
                ]
            },
        ),
    )

    response = get(api_client, token, url("chats", integration))

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json() == [
        {"id": "c1", "name": "Launch", "chat_type": "group"},
        {"id": "c2", "name": "Bob", "chat_type": "oneOnOne"},
        {"id": "c3", "name": "Carol, dave@contoso.com", "chat_type": "group"},
    ]
    assert request.call_args.kwargs["url"] == f"{GRAPH}/me/chats"
    assert request.call_args.kwargs["params"] == {
        "$top": "50",
        "$orderby": "lastMessagePreview/createdDateTime desc",
        "$expand": "members",
    }


def test_answers_are_cached_per_integration(
    api_client, enterprise_data_fixture, mocker
):
    token, integration = setup(enterprise_data_fixture)
    request = mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(200, {"value": [{"id": "t1", "displayName": "A"}]}),
    )

    get(api_client, token, url("teams", integration))
    response = get(api_client, token, url("teams", integration))

    assert response.json() == [{"id": "t1", "name": "A"}]
    assert request.call_count == 1

    # Signing in again starts afresh.
    integration.generation += 1
    integration.save()
    get(api_client, token, url("teams", integration))
    assert request.call_count == 2


def test_errors_are_safe_to_show(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture)
    mocker.patch(
        GRAPH_REQUEST,
        return_value=FakeResponse(
            403, {"error": {"code": "Forbidden", "message": "secret"}}
        ),
    )

    response = get(api_client, token, url("teams", integration))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_MICROSOFT_TEAMS_PICKER"
    assert "isn't allowed" in response.json()["detail"]
    assert "secret" not in response.json()["detail"]


def test_a_disconnected_account_asks_to_reconnect(
    api_client, enterprise_data_fixture, mocker
):
    token, integration = setup(enterprise_data_fixture, refresh_token="")
    request = mocker.patch(GRAPH_REQUEST)

    response = get(api_client, token, url("teams", integration))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "Reconnect" in response.json()["detail"]
    request.assert_not_called()


def test_missing_permissions_are_reported(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(
        enterprise_data_fixture, scopes=["openid", "profile", "email", "User.Read"]
    )
    request = mocker.patch(GRAPH_REQUEST)

    response = get(api_client, token, url("chats", integration))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "send Teams messages" in response.json()["detail"]
    request.assert_not_called()


def test_a_personal_account_is_refused(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture, tenant_id=PERSONAL_TENANT_ID)
    request = mocker.patch(GRAPH_REQUEST)

    response = get(api_client, token, url("teams", integration))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "work or school" in response.json()["detail"]
    request.assert_not_called()


def test_without_license(api_client, enterprise_data_fixture, mocker):
    token, integration = setup(enterprise_data_fixture)
    enterprise_data_fixture.delete_all_licenses()
    request = mocker.patch(GRAPH_REQUEST)

    response = get(api_client, token, url("teams", integration))

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"
    request.assert_not_called()


def test_someone_else_s_integration(api_client, enterprise_data_fixture, mocker):
    _, integration = setup(enterprise_data_fixture)
    _, other_token = enterprise_data_fixture.create_user_and_token()
    request = mocker.patch(GRAPH_REQUEST)

    response = get(api_client, other_token, url("teams", integration))

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    request.assert_not_called()


def test_an_integration_of_another_type(api_client, enterprise_data_fixture, mocker):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_builder_application(user=user)
    integration = enterprise_data_fixture.create_slack_bot_integration(
        application=builder, token="x"
    )

    response = get(api_client, token, url("teams", integration))

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_INTEGRATION_DOES_NOT_EXIST"
