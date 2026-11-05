from datetime import datetime, timezone
from unittest.mock import patch

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.core.models import Workspace


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_list_admin_workspaces(api_client, data_fixture, django_assert_num_queries):
    """
    This endpoint doesn't need to be tested extensively because it uses the same base
    class as the list users endpoint which already has extensive tests. We only need to
    test if the functionality works in a basic form.
    """

    created = datetime(2020, 4, 10, 0, 0, 0).replace(tzinfo=timezone.utc)
    staff_user, staff_token = data_fixture.create_user_and_token(is_staff=True)
    normal_user, normal_token = data_fixture.create_user_and_token()
    workspace_1 = data_fixture.create_workspace(name="A")
    workspace_1.created_on = created
    workspace_1.save()
    workspace_2 = data_fixture.create_workspace(name="B", created_on=created)
    workspace_2.created_on = created
    workspace_2.save()
    template_workspace = data_fixture.create_workspace(
        name="Template", created_on=created
    )
    data_fixture.create_template(workspace=template_workspace)
    data_fixture.create_user_workspace(
        workspace=workspace_1, user=normal_user, permissions="MEMBER"
    )
    data_fixture.create_user_workspace(
        workspace=workspace_2, user=normal_user, permissions="ADMIN"
    )
    data_fixture.create_database_application(workspace=workspace_1)
    data_fixture.create_database_application(workspace=workspace_1)

    response = api_client.get(
        reverse("api:admin:workspaces:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    with django_assert_num_queries(6):
        response = api_client.get(
            reverse("api:admin:workspaces:list"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {staff_token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": workspace_1.id,
                "name": workspace_1.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "MEMBER",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 2,
                "created_on": "2020-04-10T00:00:00Z",
            },
            {
                "id": workspace_2.id,
                "name": workspace_2.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "ADMIN",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 0,
                "created_on": "2020-04-10T00:00:00Z",
            },
        ],
    }

    response = api_client.get(
        f"{reverse('api:admin:workspaces:list')}?search={workspace_1.name}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {staff_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": workspace_1.id,
                "name": workspace_1.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "MEMBER",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 2,
                "created_on": "2020-04-10T00:00:00Z",
            },
        ],
    }

    response = api_client.get(
        f"{reverse('api:admin:workspaces:list')}?sorts=-name",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {staff_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": workspace_2.id,
                "name": workspace_2.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "ADMIN",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 0,
                "created_on": "2020-04-10T00:00:00Z",
            },
            {
                "id": workspace_1.id,
                "name": workspace_1.name,
                "users": [
                    {
                        "id": normal_user.id,
                        "email": normal_user.email,
                        "permissions": "MEMBER",
                    }
                ],
                "free_users": None,
                "row_count": 0,
                "seats_taken": None,
                "storage_usage": None,
                "application_count": 2,
                "created_on": "2020-04-10T00:00:00Z",
            },
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_delete_workspace(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token()
    staff_user, staff_token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace()

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": 99999})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {staff_token}")
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GROUP_DOES_NOT_EXIST"

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {normal_token}")
    assert response.status_code == HTTP_403_FORBIDDEN

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {staff_token}")
    assert response.status_code == 204
    assert Workspace.objects.all().count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_delete_template_workspace(api_client, data_fixture):
    staff_user, staff_token = data_fixture.create_user_and_token(is_staff=True)
    workspace = data_fixture.create_workspace()
    data_fixture.create_template(workspace=workspace)

    url = reverse("api:admin:workspaces:edit", kwargs={"workspace_id": workspace.id})
    response = api_client.delete(url, HTTP_AUTHORIZATION=f"JWT {staff_token}")
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DELETE_A_TEMPLATE_GROUP"
    assert Workspace.objects.all().count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_non_admin_list_workspaces_as_options(api_client, data_fixture):
    (
        admin_user,
        admin_token,
    ) = data_fixture.create_user_and_token()

    # no search query should return all workspaces
    response = api_client.get(
        reverse("api:admin:workspaces:options"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_list_workspaces_as_options(api_client, data_fixture):
    (
        admin_user,
        admin_token,
    ) = data_fixture.create_user_and_token(is_staff=True)
    workspace_1 = data_fixture.create_workspace(name="workspace 1", user=admin_user)
    workspace_2 = data_fixture.create_workspace(name="workspace 2", user=admin_user)

    # no search query should return all workspaces
    response = api_client.get(
        reverse("api:admin:workspaces:options"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": workspace_1.id, "value": workspace_1.name},
            {"id": workspace_2.id, "value": workspace_2.name},
        ],
    }

    # searching by name should return only the correct workspace
    response = api_client.get(
        reverse("api:admin:workspaces:options") + "?search=1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": workspace_1.id, "value": workspace_1.name}],
    }


@pytest.mark.django_db
@pytest.mark.parametrize("search", ["", "workspace"])
def test_workspace_options_estimate_expensive_counts(api_client, data_fixture, search):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    first = data_fixture.create_workspace(name="workspace 1")
    data_fixture.create_workspace(name="workspace 2")
    # A selective search can estimate few matches while still scanning the whole
    # table. It must not fall back to COUNT(*) when the plan is expensive.
    plan = '[{"Plan": {"Plan Rows": 42, "Total Cost": 300000}}]'
    with (
        patch("django.db.models.query.QuerySet.explain", return_value=plan) as explain,
        patch(
            "django.db.models.query.QuerySet.count",
            side_effect=AssertionError(
                "Workspace options must not count an expensive query"
            ),
        ),
    ):
        response = api_client.get(
            reverse("api:admin:workspaces:options"),
            {"size": 1, "search": search},
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    explain.assert_called_once_with(format="json")
    assert response.json() == {
        "count": 42,
        "next": f"http://testserver/api/admin/workspaces/options/?page=2&search={search}&size=1",
        "previous": None,
        "results": [{"id": first.id, "value": first.name}],
    }


@pytest.mark.django_db
@pytest.mark.parametrize("estimate", [0, 42])
@pytest.mark.parametrize("filter_type", ["all", "search", "ids"])
def test_workspace_options_keep_all_pages_reachable_when_count_is_underestimated(
    api_client, data_fixture, estimate, filter_type
):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    workspaces = [
        data_fixture.create_workspace(name=f"workspace {i:03}") for i in range(201)
    ]
    query = {"size": 100}
    if filter_type == "search":
        query["search"] = "workspace"
        data_fixture.create_workspace(name="Another name")
    elif filter_type == "ids":
        query["ids"] = ",".join(str(workspace.id) for workspace in workspaces)
        data_fixture.create_workspace(name="Another name")
    plan = f'[{{"Plan": {{"Plan Rows": {estimate}, "Total Cost": 300000}}}}]'
    with (
        patch("django.db.models.query.QuerySet.explain", return_value=plan),
        patch(
            "django.db.models.query.QuerySet.count",
            side_effect=AssertionError("An expensive count must stay estimated"),
        ),
    ):
        for page in (1, 2, 3):
            response = api_client.get(
                reverse("api:admin:workspaces:options"),
                {**query, "page": page},
                HTTP_AUTHORIZATION=f"JWT {token}",
            )
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert set(data) == {"count", "next", "previous", "results"}
            assert data["results"] == [
                {"id": workspace.id, "value": workspace.name}
                for workspace in workspaces[(page - 1) * 100 : page * 100]
            ]
            assert data["count"] == (101 if page == 1 else 201)
            assert (data["previous"] is not None) == (page > 1)
            assert (data["next"] is not None) == (page < 3)
            if page < 3:
                # CrudTable derives page availability from count rather than next.
                assert data["count"] > page * 100


@pytest.mark.django_db
def test_workspace_options_correct_an_overestimate_at_the_observed_end(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    workspaces = [
        data_fixture.create_workspace(name=f"workspace {i}") for i in range(2)
    ]
    with (
        patch(
            "django.db.models.query.QuerySet.explain",
            return_value='[{"Plan": {"Plan Rows": 10000, "Total Cost": 300000}}]',
        ),
        patch(
            "django.db.models.query.QuerySet.count",
            side_effect=AssertionError("An expensive count must stay estimated"),
        ),
    ):
        response = api_client.get(
            reverse("api:admin:workspaces:options"),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [{"id": w.id, "value": w.name} for w in workspaces],
    }


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["last", "invalid", "0", "-1"])
def test_workspace_options_page_selection_uses_corrected_estimates(
    api_client, data_fixture, page
):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    workspaces = [
        data_fixture.create_workspace(name=f"workspace {i:03}") for i in range(101)
    ]
    with patch(
        "django.db.models.query.QuerySet.explain",
        return_value='[{"Plan": {"Plan Rows": 0, "Total Cost": 300000}}]',
    ):
        response = api_client.get(
            reverse("api:admin:workspaces:options"),
            {"page": page},
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 101
    assert response.json()["next"] is not None
    assert response.json()["previous"] is None
    assert [w["id"] for w in response.json()["results"]] == [
        w.id for w in workspaces[:100]
    ]


@pytest.mark.django_db
def test_workspace_options_empty_stale_page_does_not_invent_an_exact_count(
    api_client, data_fixture
):
    _, token = data_fixture.create_user_and_token(is_staff=True)
    data_fixture.create_workspace()
    with patch(
        "django.db.models.query.QuerySet.explain",
        return_value='[{"Plan": {"Plan Rows": 42, "Total Cost": 300000}}]',
    ):
        response = api_client.get(
            reverse("api:admin:workspaces:options"),
            {"page": 2},
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 42
    assert response.json()["next"] is None
    assert response.json()["previous"] is not None
    assert response.json()["results"] == []


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_list_workspaces_as_options_filter_by_ids(api_client, data_fixture):
    (
        admin_user,
        admin_token,
    ) = data_fixture.create_user_and_token(is_staff=True)
    workspace_1 = data_fixture.create_workspace(name="workspace 1", user=admin_user)
    workspace_2 = data_fixture.create_workspace(name="workspace 2", user=admin_user)
    data_fixture.create_workspace(name="workspace 3", user=admin_user)

    # filtering by a single id should return only that workspace
    response = api_client.get(
        reverse("api:admin:workspaces:options") + f"?ids={workspace_1.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": workspace_1.id, "value": workspace_1.name}],
    }

    # filtering by multiple ids should return all matching workspaces
    response = api_client.get(
        reverse("api:admin:workspaces:options")
        + f"?ids={workspace_1.id},{workspace_2.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [
            {"id": workspace_1.id, "value": workspace_1.name},
            {"id": workspace_2.id, "value": workspace_2.name},
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_list_workspaces_as_options_filter_by_invalid_ids(
    api_client, data_fixture
):
    _, admin_token = data_fixture.create_user_and_token(is_staff=True)

    # Negative IDs should be rejected.
    response = api_client.get(
        reverse("api:admin:workspaces:options") + "?ids=-1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response.json()["detail"]["ids"] == [
        {
            "code": "invalid",
            "error": "'-1' is not a valid ID. Only positive integers are accepted.",
        }
    ]

    # Non-numeric values should be rejected.
    response = api_client.get(
        reverse("api:admin:workspaces:options") + "?ids=abc",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response.json()["detail"]["ids"] == [
        {
            "code": "invalid",
            "error": "'abc' is not a valid ID. Only positive integers are accepted.",
        }
    ]

    # A mix of valid and invalid values should still be rejected.
    response = api_client.get(
        reverse("api:admin:workspaces:options") + "?ids=1,-2,3",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert response.json()["detail"]["ids"] == [
        {
            "code": "invalid",
            "error": "'-2' is not a valid ID. Only positive integers are accepted.",
        }
    ]

    # Newline in ids should return 400, not 500.
    response = api_client.get(
        reverse("api:admin:workspaces:options") + "?ids=1%0A2",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
