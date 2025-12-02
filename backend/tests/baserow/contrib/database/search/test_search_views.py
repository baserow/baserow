from django.db import transaction
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchMode
from baserow.test_utils.helpers import setup_interesting_test_table

pytestmark = pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)


@pytest.mark.django_db
def test_search_grid_with_invalid_mode(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    view = data_fixture.create_grid_view(user=user)

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={"search": "economy", "search_mode": "slow"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json == {
        "detail": {
            "search_mode": [
                {"code": "invalid_choice", "error": '"slow" is not a valid choice.'}
            ]
        },
        "error": "ERROR_QUERY_PARAMETER_VALIDATION",
    }


@pytest.mark.django_db
def test_search_grid_with_compat_mode(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()

    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)
    view = data_fixture.create_grid_view(user=user, table=table)

    RowHandler().create_row(
        user=user,
        table=table,
        values={
            text_field.id: "economy",
        },
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={"search": "economy", "search_mode": SearchMode.COMPAT},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                text_field.db_column: "economy",
            }
        ],
    }


@pytest.mark.django_db
def test_search_grid_with_full_text_disabled_compat_mode_used(
    api_client, data_fixture, disable_full_text_search
):
    user, jwt_token = data_fixture.create_user_and_token()

    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)
    view = data_fixture.create_grid_view(user=user, table=table)

    RowHandler().create_row(
        user=user,
        table=table,
        values={
            text_field.id: "economy",
        },
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={
            "search": "economy",
            "search_mode": SearchMode.FT_WITH_COUNT,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                text_field.db_column: "economy",
            }
        ],
    }


@pytest.mark.django_db
def test_count_grid_with_compat_mode(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()

    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)
    view = data_fixture.create_grid_view(user=user, table=table)

    RowHandler().create_row(
        user=user,
        table=table,
        values={
            text_field.id: "economy",
        },
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={
            "count": True,
            "search": "economy",
            "search_mode": SearchMode.COMPAT,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {"count": 1}


@pytest.mark.django_db(transaction=True)
def test_search_grid_with_full_text_with_count_mode(api_client, data_fixture):
    with transaction.atomic():
        user, jwt_token = data_fixture.create_user_and_token()
        table = data_fixture.create_database_table(user=user)
        text_field = data_fixture.create_text_field(
            table=table, name="text_field", order=0
        )
        view = data_fixture.create_grid_view(user=user, table=table)

        RowHandler().create_row(
            user=user,
            table=table,
            values={
                text_field.id: "economy",
            },
        )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={
            "search": "economy",
            "search_mode": SearchMode.FT_WITH_COUNT,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                text_field.db_column: "economy",
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
def test_count_grid_with_full_text_with_count_mode(api_client, data_fixture):
    with transaction.atomic():
        user, jwt_token = data_fixture.create_user_and_token()
        table = data_fixture.create_database_table(user=user)
        text_field = data_fixture.create_text_field(
            table=table, name="text_field", order=0
        )
        view = data_fixture.create_grid_view(user=user, table=table)

        RowHandler().create_row(
            user=user,
            table=table,
            values={
                text_field.id: "economy",
            },
        )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={
            "count": True,
            "search": "economy",
            "search_mode": SearchMode.FT_WITH_COUNT,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {"count": 1}


@pytest.mark.django_db(transaction=True)
def test_can_create_and_index_and_search_interesting_test_table(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()
    table, _, _, _, _ = setup_interesting_test_table(
        data_fixture,
        user,
    )
    view = data_fixture.create_grid_view(user=user, table=table)

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={
            "search": "a.txt",
            "search_mode": SearchMode.FT_WITH_COUNT,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1


@pytest.mark.django_db
def test_search_grid_defaults_to_compat_mode_when_env_var_not_set(
    api_client, data_fixture
):
    user, jwt_token = data_fixture.create_user_and_token()

    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)
    view = data_fixture.create_grid_view(user=user, table=table)

    RowHandler().create_row(
        user=user,
        table=table,
        values={
            text_field.id: "econ#$%omy",
        },
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={"search": "#$%"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 1,
                "order": "1.00000000000000000000",
                text_field.db_column: "econ#$%omy",
            }
        ],
    }


@pytest.mark.django_db
@override_settings(DEFAULT_SEARCH_MODE=SearchMode.FT_WITH_COUNT)
def test_search_grid_defaults_to_mode_set_via_env_var(api_client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()

    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field", order=0)
    view = data_fixture.create_grid_view(user=user, table=table)

    RowHandler().create_row(
        user=user,
        table=table,
        values={
            text_field.id: "econ#$%omy",
        },
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:list",
            kwargs={"view_id": view.id},
        ),
        data={"search": "#$%"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }
