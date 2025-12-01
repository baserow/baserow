import json

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from pytest_unordered import unordered
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import ALL_SEARCH_MODES, SearchHandler
from baserow.test_utils.helpers import is_dict_subset


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_without_valid_premium_license(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=False
    )
    timeline = premium_data_fixture.create_timeline_view(user=user)
    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    # The timeline view should work if it's a template.

    premium_data_fixture.create_template(workspace=timeline.table.database.workspace)

    timeline.table.database.workspace.has_template.cache_clear()

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.view_calendar
@override_settings(DEBUG=True)
def test_list_without_valid_premium_license_for_workspace(
    api_client, premium_data_fixture, alternative_per_workspace_license_service
):
    # without a license

    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    timeline = premium_data_fixture.create_timeline_view(user=user)
    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"

    # with a valid license

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [timeline.table.database.workspace.id]
    )
    premium_data_fixture.create_template(workspace=timeline.table.database.workspace)

    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    timeline = premium_data_fixture.create_timeline_view(table=table)
    timeline_2 = premium_data_fixture.create_timeline_view()

    model = timeline.table.get_model()
    row_1 = model.objects.create(**{f"field_{text_field.id}": "Green"})
    row_2 = model.objects.create()
    row_3 = model.objects.create(**{f"field_{text_field.id}": "Orange"})
    row_4 = model.objects.create(**{f"field_{text_field.id}": "Purple"})

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": 999})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TIMELINE_DOES_NOT_EXIST"

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline_2.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(
        url, {"limit": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id
    assert "field_options" not in response_json

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(
        url, {"limit": 1, "offset": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_3.id

    sort = premium_data_fixture.create_view_sort(
        view=timeline, field=text_field, order="ASC"
    )
    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_4.id
    assert response_json["results"][3]["id"] == row_2.id
    sort.delete()

    view_filter = premium_data_fixture.create_view_filter(
        view=timeline, field=text_field, value="Green"
    )
    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_1.id
    view_filter.delete()

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(
        url, data={"count": ""}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response_json["count"] == 4
    assert len(response_json.keys()) == 1

    row_1.delete()
    row_2.delete()
    row_3.delete()
    row_4.delete()

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 0
    assert not response_json["previous"]
    assert not response_json["next"]
    assert len(response_json["results"]) == 0

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    premium_data_fixture.create_template(workspace=timeline.table.database.workspace)
    timeline.table.database.workspace.has_template.cache_clear()
    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_timeline_rows_adhoc_filtering_query_param_filter(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="normal")
    # hidden field should behave the same as normal one
    text_field_hidden = premium_data_fixture.create_text_field(
        table=table, name="hidden"
    )
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, create_options=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, text_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, text_field_hidden, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"normal": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"normal": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    get_params = [f"filter__field_{text_field.id}__contains=a"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    get_params = [
        f"filter__field_{text_field.id}__contains=a",
        f"filter__field_{text_field.id}__contains=b",
        f"filter_type=OR",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    get_params = [f"filter__field_{text_field_hidden.id}__contains=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    get_params = [f"filter__field_{text_field.id}__random=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    get_params = [f"filter__field_{text_field.id}__higher_than=1"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_timeline_rows_adhoc_filtering_invalid_advanced_filters(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text_field")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True, create_options=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, text_field, hidden=False
    )

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )

    expected_errors = [
        (
            "invalid_json",
            {
                "error": "The provided filters are not valid JSON.",
                "code": "invalid_json",
            },
        ),
        (
            json.dumps({"filter_type": "invalid"}),
            {
                "filter_type": [
                    {
                        "error": '"invalid" is not a valid choice.',
                        "code": "invalid_choice",
                    }
                ]
            },
        ),
        (
            json.dumps(
                {"filter_type": "OR", "filters": "invalid", "groups": "invalid"}
            ),
            {
                "filters": [
                    {
                        "error": 'Expected a list of items but got type "str".',
                        "code": "not_a_list",
                    }
                ],
                "groups": {
                    "non_field_errors": [
                        {
                            "error": 'Expected a list of items but got type "str".',
                            "code": "not_a_list",
                        }
                    ],
                },
            },
        ),
    ]

    for filters, error_detail in expected_errors:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"
        assert response_json["detail"] == error_detail


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_timeline_rows_adhoc_filtering_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text_field")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True, create_options=False
    )
    premium_data_fixture.create_timeline_view_field_option(timeline_view, text_field)

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }
    get_params = [
        "filters=" + json.dumps(advanced_filters),
        f"filter__field_{text_field.id}__equal=z",
        f"filter_type=AND",
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_timeline_rows_adhoc_filtering_overrides_existing_filters(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text_field")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True, create_options=False
    )
    # in usual scenario this filter would filtered out all rows
    equal_filter = premium_data_fixture.create_view_filter(
        view=timeline_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    advanced_filters = {
        "filter_type": "OR",
        "filters": [
            {
                "field": text_field.id,
                "type": "equal",
                "value": "a",
            },
            {
                "field": text_field.id,
                "type": "equal",
                "value": "b",
            },
        ],
    }

    get_params = [
        "filters=" + json.dumps(advanced_filters),
    ]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_timeline_rows_adhoc_filtering_advanced_filters(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    # hidden fields should behave like normal ones
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True, create_options=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )
    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "contains",
                "value": "a",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "OR",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "b",
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    # groups can be arbitrarily nested
    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "",
                    },
                ],
                "groups": [
                    {
                        "filter_type": "OR",
                        "filters": [
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "a",
                            },
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "b",
                            },
                        ],
                    },
                ],
            },
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": hidden_field.id,
                "type": "contains",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "random",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "higher_than",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    for filters in [
        "invalid_json",
        json.dumps({"filter_type": "invalid"}),
        json.dumps({"filter_type": "OR", "filters": "invalid"}),
    ]:
        get_params = [f"filters={filters}"]
        response = api_client.get(
            f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_include_field_options(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )
    table = premium_data_fixture.create_database_table(user=user)
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)
    timeline = premium_data_fixture.create_timeline_view(
        table=table,
        start_date_field=start_date_field,
        end_date_field=end_date_field,
        create_options=True,
    )

    # This field is deliberately created after the creation of the timeline fields
    # so that the TimelineViewFieldOptions entry is not created. This should
    # automatically be created when the page is fetched.
    text_field = premium_data_fixture.create_text_field(table=table)

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "field_options" not in response_json

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(
        url, {"include": "field_options"}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 3
    assert response_json["field_options"][str(start_date_field.id)]["hidden"] is False
    assert response_json["field_options"][str(start_date_field.id)]["order"] == 32767
    assert response_json["field_options"][str(end_date_field.id)]["hidden"] is False
    assert response_json["field_options"][str(end_date_field.id)]["order"] == 32767
    assert response_json["field_options"][str(text_field.id)]["hidden"] is True
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    assert "filters_disabled" not in response_json


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
@pytest.mark.parametrize("search_mode", ALL_SEARCH_MODES)
def test_list_rows_search(api_client, premium_data_fixture, search_mode):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(
        table=table, order=0, name="Name", text_default=""
    )
    timeline = premium_data_fixture.create_timeline_view(table=table)
    search_term = "Smith"
    model = timeline.table.get_model()
    not_matching_row1 = model.objects.create(
        **{f"field_{text_field.id}": "Mark Spencer"}
    )
    matching_row1 = model.objects.create(
        **{f"field_{text_field.id}": f"Elon {search_term}"}
    )
    matching_row2 = model.objects.create(
        **{f"field_{text_field.id}": f"James {search_term}"}
    )
    not_matching_row2 = model.objects.create(
        **{f"field_{text_field.id}": "Robin Backham"}
    )

    SearchHandler.update_search_data(table)

    url = reverse("api:database:views:timeline:list", kwargs={"view_id": timeline.id})
    response = api_client.get(
        url,
        {"search": search_term, "search_mode": search_mode},
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 2
    assert response_json["results"][0]["id"] == matching_row1.id
    assert response_json["results"][1]["id"] == matching_row2.id


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_patch_timeline_view_field_options(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table)
    timeline = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    url = reverse("api:database:views:field_options", kwargs={"view_id": timeline.id})
    response = api_client.patch(
        url,
        {"field_options": {text_field.id: {"width": 300, "hidden": False}}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 1
    assert response_json["field_options"][str(text_field.id)]["hidden"] is False
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    options = timeline.get_field_options()
    assert len(options) == 1
    assert options[0].field_id == text_field.id
    assert options[0].hidden is False
    assert options[0].order == 32767


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_create_timeline_view(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    start_date_field = premium_data_fixture.create_date_field(table=table)
    end_date_field = premium_data_fixture.create_date_field(table=table)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "filter_type": "AND",
            "filters_disabled": False,
            "start_date_field": start_date_field.id,
            "end_date_field": end_date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response.json()
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "timeline"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False
    assert response_json["start_date_field"] == start_date_field.id
    assert response_json["end_date_field"] == end_date_field.id


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_cant_create_timeline_view_invalid_date_fields(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    start_date_field = premium_data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    end_date_field = premium_data_fixture.create_date_field(table=table)
    wrong_type_field = premium_data_fixture.create_text_field(table=table)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 2", "type": "timeline"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": None,
            "end_date_field": None,
        },
        response.json(),
    )

    # But it's not possible to create a timeline view with a start or an end date field
    # that is not a date field
    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": wrong_type_field.id,
            "end_date_field": end_date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INCOMPATIBLE_FIELD"
    assert response_json["detail"] == "The provided field is not compatible."

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": start_date_field.id,
            "end_date_field": wrong_type_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INCOMPATIBLE_FIELD"
    assert response_json["detail"] == "The provided field is not compatible."

    # They must both have the same include_time value and the same timezone
    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": start_date_field.id,
            "end_date_field": end_date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS"

    start_date_field.date_force_timezone = "Europe/Rome"
    start_date_field.save()
    end_date_field.date_include_time = True
    end_date_field.save()

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": start_date_field.id,
            "end_date_field": end_date_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_update_timeline_view(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    date_field_1 = premium_data_fixture.create_date_field(table=table)
    date_field_2 = premium_data_fixture.create_date_field(table=table)
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, start_date_field=None, end_date_field=None
    )

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": timeline_view.id}),
        {"name": "Test 2", "type": "timeline"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": None,
            "end_date_field": None,
        },
        response_json,
    )

    # can set the start and end date fields
    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": timeline_view.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": date_field_1.id,
            "end_date_field": date_field_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": date_field_1.id,
            "end_date_field": date_field_2.id,
        },
        response_json,
    )

    date_field_1.date_include_time = True
    date_field_2.date_include_time = True

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": timeline_view.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": date_field_2.id,
            "end_date_field": date_field_1.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": date_field_2.id,
            "end_date_field": date_field_1.id,
        },
        response_json,
    )

    # Wit the same timezone it should be possible to set the start and end date fields
    date_field_1.date_force_timezone = "Europe/Rome"
    date_field_1.save()
    date_field_2.date_force_timezone = "Europe/Rome"
    date_field_2.save()

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": timeline_view.id}),
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": date_field_1.id,
            "end_date_field": date_field_2.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert is_dict_subset(
        {
            "name": "Test 2",
            "type": "timeline",
            "start_date_field": date_field_1.id,
            "end_date_field": date_field_2.id,
        },
        response_json,
    )


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_get_public_timeline_view(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    start_date_field = premium_data_fixture.create_date_field(table=table, name="Start")
    end_date_field = premium_data_fixture.create_date_field(table=table, name="End")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table,
        user=user,
        public=True,
        start_date_field=start_date_field,
        end_date_field=end_date_field,
    )

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    # This view sort shouldn't be exposed as it is for a hidden field
    premium_data_fixture.create_view_sort(
        view=timeline_view, field=hidden_field, order="ASC"
    )
    visible_sort = premium_data_fixture.create_view_sort(
        view=timeline_view, field=public_field, order="DESC"
    )

    # View filters should not be returned at all for any and all fields regardless of
    # if they are hidden.
    premium_data_fixture.create_view_filter(
        view=timeline_view, field=hidden_field, type="contains", value="hidden"
    )
    premium_data_fixture.create_view_filter(
        view=timeline_view, field=public_field, type="contains", value="public"
    )

    # Can access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": timeline_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "fields": unordered(
            [
                {
                    "id": public_field.id,
                    "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "name": "public",
                    "order": 0,
                    "primary": False,
                    "text_default": "",
                    "type": "text",
                    "read_only": False,
                    "description": None,
                    "immutable_properties": False,
                    "immutable_type": False,
                    "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "db_index": False,
                    "field_constraints": [],
                },
                {
                    "id": start_date_field.id,
                    "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "name": "Start",
                    "order": 0,
                    "primary": False,
                    "date_include_time": False,
                    "date_format": "EU",
                    "date_time_format": "24",
                    "date_show_tzinfo": False,
                    "date_force_timezone": None,
                    "type": "date",
                    "read_only": False,
                    "description": None,
                    "immutable_properties": False,
                    "immutable_type": False,
                    "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "db_index": False,
                    "field_constraints": [],
                },
                {
                    "id": end_date_field.id,
                    "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "name": "End",
                    "order": 0,
                    "primary": False,
                    "date_include_time": False,
                    "date_force_timezone": None,
                    "date_format": "EU",
                    "date_time_format": "24",
                    "date_show_tzinfo": False,
                    "type": "date",
                    "read_only": False,
                    "description": None,
                    "immutable_properties": False,
                    "immutable_type": False,
                    "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "db_index": False,
                    "field_constraints": [],
                },
            ]
        ),
        "view": {
            "id": timeline_view.slug,
            "name": timeline_view.name,
            "order": 0,
            "public": True,
            "slug": timeline_view.slug,
            "sortings": [
                # Note the sorting for the hidden field is not returned
                {
                    "field": visible_sort.field.id,
                    "id": visible_sort.id,
                    "order": "DESC",
                    "type": "default",
                    "view": timeline_view.slug,
                }
            ],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "show_logo": True,
            "allow_public_export": False,
            "type": "timeline",
            "start_date_field": start_date_field.id,
            "end_date_field": end_date_field.id,
            "timescale": "month",
        },
    }


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_public_doesnt_show_hidden_columns(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    start_date_field = premium_data_fixture.create_date_field(table=table, name="Start")
    end_date_field = premium_data_fixture.create_date_field(table=table, name="End")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table,
        user=user,
        public=True,
        start_date_field=start_date_field,
        end_date_field=end_date_field,
    )

    public_field_option = premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    RowHandler().create_row(user, table, values={})

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:timeline:public_rows",
            kwargs={"slug": timeline_view.slug},
        )
        + "?include=field_options"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                f"field_{public_field.id}": None,
                f"field_{start_date_field.id}": None,
                f"field_{end_date_field.id}": None,
                "id": 1,
                "order": "1.00000000000000000000",
            }
        ],
        "field_options": {
            f"{public_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
            },
            f"{start_date_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
            },
            f"{end_date_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
            },
        },
    }


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_public_with_query_param_filter(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__contains=a"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    get_params = [
        f"filter__field_{public_field.id}__contains=a",
        f"filter__field_{public_field.id}__contains=b",
        f"filter_type=OR",
    ]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    get_params = [f"filter__field_{hidden_field.id}__contains=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__random=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__higher_than=1"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_public_with_query_param_order(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    password_field = premium_data_fixture.create_password_field(
        table=table, name="password"
    )
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, password_field, hidden=False
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    second_row = RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=-field_{public_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == second_row.id
    assert response_json["results"][1]["id"] == first_row.id

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=field_{hidden_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=field_{password_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_public_filters_by_visible_and_hidden_columns(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True
    )

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    premium_data_fixture.create_view_filter(
        view=timeline_view, field=hidden_field, type="equal", value="y"
    )
    premium_data_fixture.create_view_filter(
        view=timeline_view, field=public_field, type="equal", value="a"
    )
    # A row whose hidden column doesn't match the first filter
    RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "not y"}, user_field_names=True
    )
    # A row whose public column doesn't match the second filter
    RowHandler().create_row(
        user, table, values={"public": "not a", "hidden": "y"}, user_field_names=True
    )
    # A row which matches all filters
    visible_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:timeline:public_rows",
            kwargs={"slug": timeline_view.slug},
        )
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["results"]) == 1
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == visible_row.id


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_public_with_query_param_advanced_filters(
    api_client, premium_data_fixture
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True, create_options=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:timeline:public_rows", kwargs={"slug": timeline_view.slug}
    )
    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "contains",
                "value": "a",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "OR",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "a",
                    },
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "b",
                    },
                ],
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    # groups can be arbitrarily nested
    advanced_filters = {
        "filter_type": "AND",
        "groups": [
            {
                "filter_type": "AND",
                "filters": [
                    {
                        "field": public_field.id,
                        "type": "contains",
                        "value": "",
                    },
                ],
                "groups": [
                    {
                        "filter_type": "OR",
                        "filters": [
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "a",
                            },
                            {
                                "field": public_field.id,
                                "type": "contains",
                                "value": "b",
                            },
                        ],
                    },
                ],
            },
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": hidden_field.id,
                "type": "contains",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "random",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    advanced_filters = {
        "filter_type": "AND",
        "filters": [
            {
                "field": public_field.id,
                "type": "higher_than",
                "value": "y",
            }
        ],
    }
    get_params = ["filters=" + json.dumps(advanced_filters)]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"

    for filters in [
        "invalid_json",
        json.dumps({"filter_type": "invalid"}),
        json.dumps({"filter_type": "OR", "filters": "invalid"}),
    ]:
        get_params = [f"filters={filters}"]
        response = api_client.get(f'{url}?{"&".join(get_params)}')
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_FILTERS_PARAM_VALIDATION_ERROR"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
@pytest.mark.parametrize("search_mode", ALL_SEARCH_MODES)
def test_list_rows_public_only_searches_by_visible_columns(
    api_client, premium_data_fixture, search_mode
):
    user, token = premium_data_fixture.create_user_and_token()
    table = premium_data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = premium_data_fixture.create_text_field(table=table, name="public")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")

    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, public=True
    )

    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, public_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )

    search_term = "search_term"
    RowHandler().create_row(
        user,
        table,
        values={"public": "other", "hidden": search_term},
        user_field_names=True,
    )
    RowHandler().create_row(
        user,
        table,
        values={"public": "other", "hidden": "other"},
        user_field_names=True,
    )
    visible_row = RowHandler().create_row(
        user,
        table,
        values={"public": search_term, "hidden": "other"},
        user_field_names=True,
    )
    SearchHandler.update_search_data(table)

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:timeline:public_rows",
            kwargs={"slug": timeline_view.slug},
        )
        + f"?search={search_term}&search_mode={search_mode}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["results"]) == 1
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == visible_row.id


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_list_rows_with_query_param_order(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)
    text_field = premium_data_fixture.create_text_field(table=table, name="text")
    hidden_field = premium_data_fixture.create_text_field(table=table, name="hidden")
    password_field = premium_data_fixture.create_password_field(
        table=table, name="password"
    )
    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, create_options=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, text_field, hidden=False
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, hidden_field, hidden=True
    )
    premium_data_fixture.create_timeline_view_field_option(
        timeline_view, password_field, hidden=False
    )
    first_row = RowHandler().create_row(
        user, table, values={"text": "a", "hidden": "a"}, user_field_names=True
    )
    second_row = RowHandler().create_row(
        user, table, values={"text": "b", "hidden": "b"}, user_field_names=True
    )
    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )

    # adhoc sorting
    response = api_client.get(
        f"{url}?order_by=-field_{text_field.id}",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == second_row.id
    assert response_json["results"][1]["id"] == first_row.id

    # adhoc sorting on hidden field
    response = api_client.get(
        f"{url}?order_by=field_{hidden_field.id}",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == first_row.id
    assert response_json["results"][1]["id"] == second_row.id

    # sorting on unsupported field
    response = api_client.get(
        f"{url}?order_by=field_{password_field.id}",
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"


@pytest.mark.django_db
@pytest.mark.view_timeline
@override_settings(DEBUG=True)
def test_cannot_list_rows_with_invalid_date_settings(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    table = premium_data_fixture.create_database_table(user=user)

    timeline_view = premium_data_fixture.create_timeline_view(
        table=table, user=user, start_date_field=None, end_date_field=None
    )

    url = reverse(
        "api:database:views:timeline:list", kwargs={"view_id": timeline_view.id}
    )

    rsp = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST
    assert rsp.json()["error"] == "ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS"

    date_field = premium_data_fixture.create_date_field(table=table)
    text_field = premium_data_fixture.create_text_field(table=table)
    timeline_view.start_date_field = text_field
    timeline_view.end_date_field = date_field
    timeline_view.save()

    rsp = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST
    assert rsp.json()["error"] == "ERROR_INCOMPATIBLE_FIELD"

    date_field = premium_data_fixture.create_date_field(table=table)
    text_field = premium_data_fixture.create_text_field(table=table)
    timeline_view.start_date_field = date_field
    timeline_view.end_date_field = text_field
    timeline_view.save()

    rsp = api_client.get(
        url,
        **{"HTTP_AUTHORIZATION": f"JWT {token}"},
    )
    assert rsp.status_code == HTTP_400_BAD_REQUEST
    assert rsp.json()["error"] == "ERROR_INCOMPATIBLE_FIELD"

    for start_date_params, end_date_params in [
        ({"date_include_time": True}, {"date_include_time": False}),
        (
            {"date_include_time": True, "date_force_timezone": "Europe/Rome"},
            {"date_include_time": False, "date_force_timezone": None},
        ),
    ]:
        start_date_field = premium_data_fixture.create_date_field(
            table=table, **start_date_params
        )
        end_date_field = premium_data_fixture.create_date_field(
            table=table, **end_date_params
        )
        timeline_view.start_date_field = start_date_field
        timeline_view.end_date_field = end_date_field
        timeline_view.save()

        rsp = api_client.get(
            url,
            **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        )
        assert rsp.status_code == HTTP_400_BAD_REQUEST
        assert rsp.json()["error"] == "ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS"

        timeline_view.start_date_field = end_date_field
        timeline_view.end_date_field = start_date_field
        timeline_view.save()

        rsp = api_client.get(
            url,
            **{"HTTP_AUTHORIZATION": f"JWT {token}"},
        )
        assert rsp.status_code == HTTP_400_BAD_REQUEST
        assert rsp.json()["error"] == "ERROR_TIMELINE_VIEW_HAS_INVALID_DATE_SETTINGS"
