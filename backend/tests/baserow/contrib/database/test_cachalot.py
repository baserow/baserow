from time import time

from django.conf import settings
from django.core.cache import caches
from django.urls import reverse

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.test_utils.helpers import AnyInt

if settings.CACHALOT_ENABLED:
    """
    Cachalot cannot be activated in a fixture because once it patches the Django ORM, it
    remains patched for the rest of the test suite. Since it's disabled by default and
    we haven't been using it lately, nor have we tested it properly after the last
    Django library update, we are disabling it for now. However, we can still enable it
    with the CACHALOT_ENABLED setting whenever we want to test it.
    """

    from cachalot.settings import cachalot_settings

    @pytest.mark.django_db(transaction=True)
    def test_cachalot_cache_count_for_filtered_views(data_fixture):
        user = data_fixture.create_user()
        table_a, _, link_field = data_fixture.create_two_linked_tables(user=user)
        cache = caches[settings.CACHALOT_CACHE]

        grid_view = data_fixture.create_grid_view(table=table_a)

        ViewHandler().create_filter(
            user=user,
            view=grid_view,
            field=link_field,
            type_name="link_row_has",
            value="1",
        )

        queries = {}

        def get_mocked_query_cache_key(compiler):
            sql, _ = compiler.as_sql()
            sql_lower = sql.lower()
            if "count(*)" in sql_lower:
                key = "count"
            elif f"database_table_{table_a.id}" in sql_lower:
                key = "select_table"
            else:
                key = f"{time()}"
            queries[key] = sql_lower
            return key

        cachalot_settings.CACHALOT_QUERY_KEYGEN = get_mocked_query_cache_key
        cachalot_settings.CACHALOT_TABLE_KEYGEN = lambda _, table: table.rsplit("_", 1)[
            1
        ]

        table_model = table_a.get_model()
        table_model.objects.create()
        queryset = ViewHandler().get_queryset(user=user, view=grid_view)

        def assert_cachalot_cache_queryset_count_of(expected_count):
            # count() should save the result of the query in the cache
            assert queryset.count() == expected_count

            # the count query has been cached
            inserted_cache_entry = cache.get("count")
            assert inserted_cache_entry is not None
            assert inserted_cache_entry[1][0] == expected_count

        assert_cachalot_cache_queryset_count_of(0)

    @pytest.mark.django_db(transaction=True)
    def test_cachalot_cache_multiple_select_correctly(api_client, data_fixture):
        user, token = data_fixture.create_user_and_token()
        database = data_fixture.create_database_application(user=user)
        table = data_fixture.create_database_table(database=database)

        field_handler = FieldHandler()
        row_handler = RowHandler()
        grid_view = data_fixture.create_grid_view(table=table)

        field = field_handler.create_field(
            user=user,
            table=table,
            name="Multiple select",
            type_name="multiple_select",
            select_options=[
                {"value": "Option 1", "color": "red"},
                {"value": "Option 2", "color": "blue"},
                {"value": "Option 3", "color": "orange"},
                {"value": "Option 4", "color": "black"},
            ],
        )

        select_options = field.select_options.all()
        model = table.get_model()

        rows = row_handler.create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": [select_options[0].id, select_options[1].value]},
                {f"field_{field.id}": [select_options[2].value, select_options[0].id]},
            ],
        ).created_rows

        url = reverse("api:database:views:grid:list", kwargs={"view_id": grid_view.id})
        response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
        response_json = response.json()
        assert response_json["count"] == 2
        assert response_json["results"][0][f"field_{field.id}"] == [
            {"id": AnyInt(), "value": "Option 1", "color": "red"},
            {"id": AnyInt(), "value": "Option 2", "color": "blue"},
        ]

        row_handler.update_rows(
            user,
            table,
            [
                {"id": rows[0].id, f"field_{field.id}": []},
            ],
            model,
            [rows[0]],
        )

        # Before #1772 this would raise an error because the cache would not be
        # correctly invalidated when updating a row so the old value would be returned.
        response = api_client.get(url, **{"HTTP_AUTHORIZATION": f"JWT {token}"})
        response_json = response.json()
        assert response_json["count"] == 2
        assert response_json["results"][0][f"field_{field.id}"] == []
