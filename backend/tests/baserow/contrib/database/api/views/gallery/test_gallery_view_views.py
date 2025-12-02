import json

from django.shortcuts import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import ALL_SEARCH_MODES, SearchHandler


@pytest.mark.django_db
def test_list_rows(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    gallery = data_fixture.create_gallery_view(table=table)
    gallery_2 = data_fixture.create_gallery_view()

    model = gallery.table.get_model()
    row_1 = model.objects.create(**{f"field_{text_field.id}": "Green"})
    row_2 = model.objects.create()
    row_3 = model.objects.create(**{f"field_{text_field.id}": "Orange"})
    row_4 = model.objects.create(**{f"field_{text_field.id}": "Purple"})

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": 999})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_GALLERY_DOES_NOT_EXIST"

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery_2.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(
        url, {"limit": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_2.id
    assert "field_options" not in response_json

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(
        url, {"limit": 1, "offset": 2}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_3.id

    sort = data_fixture.create_view_sort(view=gallery, field=text_field, order="ASC")
    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 4
    assert response_json["results"][0]["id"] == row_1.id
    assert response_json["results"][1]["id"] == row_3.id
    assert response_json["results"][2]["id"] == row_4.id
    assert response_json["results"][3]["id"] == row_2.id
    sort.delete()

    view_filter = data_fixture.create_view_filter(
        view=gallery, field=text_field, value="Green"
    )
    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == row_1.id
    view_filter.delete()

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
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

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["count"] == 0
    assert not response_json["previous"]
    assert not response_json["next"]
    assert len(response_json["results"]) == 0

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_401_UNAUTHORIZED

    data_fixture.create_template(workspace=gallery.table.database.workspace)
    gallery.table.database.workspace.has_template.cache_clear()
    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_list_gallery_rows_adhoc_filtering_query_param_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="normal")
    # hidden field should behave the same as normal one
    text_field_hidden = data_fixture.create_text_field(table=table, name="hidden")
    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, create_options=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, text_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, text_field_hidden, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"normal": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"normal": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
    )
    get_params = [f"filter__field_{text_field_hidden.id}__contains=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
    )
    get_params = [f"filter__field_{text_field.id}__random=y"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
    )
    get_params = [f"filter__field_{text_field.id}__higher_than=1"]
    response = api_client.get(
        f'{url}?{"&".join(get_params)}', HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
def test_list_gallery_rows_adhoc_filtering_invalid_advanced_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, text_field, hidden=False
    )

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
def test_list_gallery_rows_adhoc_filtering_advanced_filters_are_preferred_to_other_filter_query_params(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_gallery_view_field_option(gallery_view, text_field)

    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
def test_list_gallery_rows_adhoc_filtering_overrides_existing_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text_field")
    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, public=True, create_options=False
    )
    # in usual scenario this filter would filtered out all rows
    equal_filter = data_fixture.create_view_filter(
        view=gallery_view, field=text_field, type="equal", value="y"
    )
    RowHandler().create_row(
        user, table, values={"text_field": "a"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"text_field": "b"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
def test_list_gallery_rows_adhoc_filtering_advanced_filters(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    # hidden fields should behave like normal ones
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
def test_list_rows_include_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Color", text_default="white"
    )
    gallery = data_fixture.create_gallery_view(table=table)

    # The second field is deliberately created after the creation of the gallery field
    # so that the GalleryViewFieldOptions entry is not created. This should
    # automatically be created when the page is fetched.
    number_field = data_fixture.create_number_field(
        table=table, order=1, name="Horsepower"
    )

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "field_options" not in response_json

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
    response = api_client.get(
        url, {"include": "field_options"}, **{"HTTP_AUTHORIZATION": f"JWT {token}"}
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["field_options"]) == 2
    assert response_json["field_options"][str(text_field.id)]["hidden"] is True
    assert response_json["field_options"][str(text_field.id)]["order"] == 32767
    assert response_json["field_options"][str(number_field.id)]["hidden"] is True
    assert response_json["field_options"][str(number_field.id)]["order"] == 32767
    assert "filters_disabled" not in response_json


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("search_mode", ALL_SEARCH_MODES)
def test_list_rows_search(api_client, data_fixture, search_mode):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(
        table=table, order=0, name="Name", text_default=""
    )
    gallery = data_fixture.create_gallery_view(table=table)
    search_term = "Smith"
    model = gallery.table.get_model()
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

    url = reverse("api:database:views:gallery:list", kwargs={"view_id": gallery.id})
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
def test_patch_gallery_view_field_options(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl",
        password="password",
        first_name="Test1",
    )
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    gallery = data_fixture.create_gallery_view(table=table)

    url = reverse("api:database:views:field_options", kwargs={"view_id": gallery.id})
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
    options = gallery.get_field_options()
    assert len(options) == 1
    assert options[0].field_id == text_field.id
    assert options[0].hidden is False
    assert options[0].order == 32767


@pytest.mark.django_db
def test_create_gallery_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test 2",
            "type": "gallery",
            "filter_type": "AND",
            "filters_disabled": False,
            "card_cover_image_field": file_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "gallery"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False
    assert response_json["card_cover_image_field"] == file_field.id


@pytest.mark.django_db
def test_create_gallery_view_invalid_card_card_cover_image_field(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text = data_fixture.create_text_field(table=table)
    file_field = data_fixture.create_file_field()

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 2", "type": "gallery", "card_cover_image_field": text.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INCOMPATIBLE_FIELD"

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {"name": "Test 2", "type": "gallery", "card_cover_image_field": file_field.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FIELD_NOT_IN_TABLE"


@pytest.mark.django_db
def test_update_gallery_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    gallery_view = data_fixture.create_gallery_view(table=table)

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": gallery_view.id}),
        {
            "name": "Test 2",
            "type": "gallery",
            "filter_type": "AND",
            "filters_disabled": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == "Test 2"
    assert response_json["type"] == "gallery"
    assert response_json["filter_type"] == "AND"
    assert response_json["filters_disabled"] is False


@pytest.mark.django_db
def test_get_public_gallery_view(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    gallery_view = data_fixture.create_gallery_view(
        table=table,
        user=user,
        public=True,
    )

    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    # This view sort shouldn't be exposed as it is for a hidden field
    data_fixture.create_view_sort(view=gallery_view, field=hidden_field, order="ASC")
    visible_sort = data_fixture.create_view_sort(
        view=gallery_view, field=public_field, order="DESC"
    )

    # View filters should not be returned at all for any and all fields regardless of
    # if they are hidden.
    data_fixture.create_view_filter(
        view=gallery_view, field=hidden_field, type="contains", value="hidden"
    )
    data_fixture.create_view_filter(
        view=gallery_view, field=public_field, type="contains", value="public"
    )

    # Can access as an anonymous user
    response = api_client.get(
        reverse("api:database:views:public_info", kwargs={"slug": gallery_view.slug})
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "fields": [
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
            }
        ],
        "view": {
            "id": gallery_view.slug,
            "name": gallery_view.name,
            "order": 0,
            "public": True,
            "slug": gallery_view.slug,
            "sortings": [
                # Note the sorting for the hidden field is not returned
                {
                    "field": visible_sort.field.id,
                    "id": visible_sort.id,
                    "order": "DESC",
                    "type": "default",
                    "view": gallery_view.slug,
                }
            ],
            "group_bys": [],
            "table": {
                "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                "id": PUBLIC_PLACEHOLDER_ENTITY_ID,
            },
            "type": "gallery",
            "card_cover_image_field": None,
            "show_logo": True,
            "allow_public_export": False,
        },
    }


@pytest.mark.django_db
def test_list_rows_public_doesnt_show_hidden_columns(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    gallery_view = data_fixture.create_gallery_view(table=table, user=user, public=True)

    public_field_option = data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    RowHandler().create_row(user, table, values={})

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
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
                "id": 1,
                "order": "1.00000000000000000000",
            }
        ],
        "field_options": {
            f"{public_field.id}": {
                "hidden": False,
                "order": public_field_option.order,
            },
        },
    }


@pytest.mark.django_db
def test_list_rows_public_with_query_param_filter(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    gallery_view = data_fixture.create_gallery_view(table=table, user=user, public=True)
    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__contains=a"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == first_row.id

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
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
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
    )
    get_params = [f"filter__field_{hidden_field.id}__contains=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_FILTER_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__random=y"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST"

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
    )
    get_params = [f"filter__field_{public_field.id}__higher_than=1"]
    response = api_client.get(f'{url}?{"&".join(get_params)}')
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD"


@pytest.mark.django_db
def test_list_rows_public_with_query_param_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    password_field = data_fixture.create_password_field(table=table, name="password")
    gallery_view = data_fixture.create_gallery_view(table=table, user=user, public=True)
    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, password_field, hidden=False
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    second_row = RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
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
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=field_{hidden_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_FOUND"

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
    )
    response = api_client.get(
        f"{url}?order_by=field_{password_field.id}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE"


@pytest.mark.django_db
def test_list_rows_public_filters_by_visible_and_hidden_columns(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    gallery_view = data_fixture.create_gallery_view(table=table, user=user, public=True)

    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    data_fixture.create_view_filter(
        view=gallery_view, field=hidden_field, type="equal", value="y"
    )
    data_fixture.create_view_filter(
        view=gallery_view, field=public_field, type="equal", value="a"
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
            "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
        )
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["results"]) == 1
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == visible_row.id


@pytest.mark.django_db
def test_list_rows_public_with_query_param_advanced_filters(api_client, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, public=True, create_options=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    first_row = RowHandler().create_row(
        user, table, values={"public": "a", "hidden": "y"}, user_field_names=True
    )
    RowHandler().create_row(
        user, table, values={"public": "b", "hidden": "z"}, user_field_names=True
    )

    url = reverse(
        "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
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


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("search_mode", ALL_SEARCH_MODES)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_list_rows_public_only_searches_by_visible_columns(
    api_client, data_fixture, search_mode
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)

    # Only information related the public field should be returned
    public_field = data_fixture.create_text_field(table=table, name="public")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")

    gallery_view = data_fixture.create_gallery_view(table=table, user=user, public=True)

    data_fixture.create_gallery_view_field_option(
        gallery_view, public_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )

    search_term = "search_term"
    RowHandler().force_create_row(
        user,
        table,
        values={"public": "other", "hidden": search_term},
        user_field_names=True,
    )
    RowHandler().force_create_row(
        user,
        table,
        values={"public": "other", "hidden": "other"},
        user_field_names=True,
    )
    visible_row = RowHandler().force_create_row(
        user,
        table,
        values={"public": search_term, "hidden": "other"},
        user_field_names=True,
    )

    # Get access as an anonymous user
    response = api_client.get(
        reverse(
            "api:database:views:gallery:public_rows", kwargs={"slug": gallery_view.slug}
        )
        + f"?search={search_term}&search_mode={search_mode}"
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert len(response_json["results"]) == 1
    assert response_json["count"] == 1
    assert response_json["results"][0]["id"] == visible_row.id


@pytest.mark.django_db
def test_list_rows_with_query_param_order(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, name="text")
    hidden_field = data_fixture.create_text_field(table=table, name="hidden")
    password_field = data_fixture.create_password_field(table=table, name="password")

    gallery_view = data_fixture.create_gallery_view(
        table=table, user=user, create_options=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, text_field, hidden=False
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, hidden_field, hidden=True
    )
    data_fixture.create_gallery_view_field_option(
        gallery_view, password_field, hidden=False
    )
    first_row = RowHandler().create_row(
        user, table, values={"text": "a", "hidden": "a"}, user_field_names=True
    )
    second_row = RowHandler().create_row(
        user, table, values={"text": "b", "hidden": "b"}, user_field_names=True
    )
    url = reverse(
        "api:database:views:gallery:list", kwargs={"view_id": gallery_view.id}
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
def test_create_gallery_view_with_lookup_as_card_card_cover_image_field(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    table_a, table_b, link = data_fixture.create_two_linked_tables(user=user)
    file_field = data_fixture.create_file_field(table=table_b)
    lookup_field = data_fixture.create_lookup_field(
        name="lookup",
        table=table_a,
        through_field=link,
        target_field=file_field,
        through_field_name=link.name,
        target_field_name=file_field.name,
    )
    formula_single_field = data_fixture.create_formula_field(
        table=table_a,
        formula="index(field('lookup'), 0)",
    )

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table_a.id}),
        {
            "name": "Test 2",
            "type": "gallery",
            "card_cover_image_field": lookup_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    gallery_id = response.json()["id"]

    response = api_client.patch(
        reverse("api:database:views:item", kwargs={"view_id": gallery_id}),
        {
            "name": "Test 2",
            "type": "gallery",
            "card_cover_image_field": formula_single_field.id,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
