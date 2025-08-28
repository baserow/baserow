import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler

pytestmark = pytest.mark.field_url


def url_formula_field_filter_proc(
    data_fixture, filter_type_name, test_value, expected_rows
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    path_field = data_fixture.create_text_field(user=user, table=table, name="path")
    field_formula = """tourl(if(field('path') !='', concat('http://example.com', field('path')), ''))"""
    formula_url_field = data_fixture.create_formula_field(
        table=table, formula=field_formula, formula_type="url"
    )
    assert formula_url_field.formula_type == "url"
    grid_view = data_fixture.create_grid_view(table=table)
    view_handler = ViewHandler()
    row_handler = RowHandler()

    view_handler.create_filter(
        user,
        grid_view,
        field=formula_url_field,
        type_name=filter_type_name,
        value=test_value,
    )
    rows = [
        {path_field.db_column: "/foo/bar"},
        {path_field.db_column: "/bar/foo"},
        {path_field.db_column: "/foo"},
        {path_field.db_column: "/bar"},
        {path_field.db_column: "/foobar"},
        {path_field.db_column: ""},
        {path_field.db_column: None},
    ]

    row_handler.create_rows(
        user=user,
        table=table,
        rows_values=rows,
        send_webhook_events=False,
        send_realtime_update=False,
    )

    q = view_handler.get_queryset(user, grid_view)
    assert len(q) == len(expected_rows)
    assert set([getattr(r, path_field.db_column) for r in q]) == set(expected_rows)


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "equal",
            "http://example.com/foobar",
            ["/foobar"],
        ),
        (
            "not_equal",
            "http://example.com/foobar",
            ["/foo/bar", "/bar/foo", "/foo", "/bar", "", None],
        ),
        (
            "contains_word",
            "foobar",
            ["/foobar"],
        ),
        (
            "doesnt_contain_word",
            "foobar",
            ["/foo/bar", "/bar/foo", "/foo", "/bar", "", None],
        ),
        (
            "contains",
            "foobar",
            ["/foobar"],
        ),
        (
            "contains_not",
            "foo",
            ["/bar", "", None],
        ),
        ("empty", "", ["", None]),
        (
            "not_empty",
            "",
            ["/foo/bar", "/bar/foo", "/foo", "/bar", "/foobar"],
        ),
        (
            "length_is_lower_than",
            "2",
            ["", None],
        ),
        (
            "length_is_lower_than",
            f"{len('http://example.com/foo/bar')}",
            [None, "", "/foobar", "/foo", "/bar"],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "equal",
            "http://example.com/foobar",
            ["/foobar"],
        ),
        (
            "equal",
            "http://example.com/invalid",
            [],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_equal_filter(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "not_equal",
            "http://example.com/foobar",
            ["/foo/bar", "/bar/foo", "/foo", "/bar", "", None],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_not_equal_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "contains_word",
            "foobar",
            ["/foobar"],
        ),
        (
            "contains_word",
            "invalid",
            [],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_contains_word_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "doesnt_contain_word",
            "foobar",
            ["/foo/bar", "/bar/foo", "/foo", "/bar", "", None],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_doesnt_contain_word_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "contains",
            "foobar",
            ["/foobar"],
        ),
        (
            "contains",
            "invalid",
            [],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_contains_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "contains_not",
            "foo",
            ["/bar", "", None],
        ),
        (
            "contains_not",
            "invalid",
            ["/foo/bar", "/foobar", "/bar/foo", "/foo", "/bar", "", None],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_contans_not_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        ("empty", "", ["", None]),
        (
            "not_empty",
            "",
            ["/foo/bar", "/bar/foo", "/foo", "/bar", "/foobar"],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_empty_not_empty_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )


@pytest.mark.parametrize(
    "filter_type_name,test_value,expected_rows",
    [
        (
            "length_is_lower_than",
            "2",
            ["", None],
        ),
        (
            "length_is_lower_than",
            f"{len('http://example.com/foo/bar')}",
            [None, "", "/foobar", "/foo", "/bar"],
        ),
    ],
)
@pytest.mark.django_db
def test_formula_url_field_length_is_lower_than_filters(
    data_fixture, filter_type_name, test_value, expected_rows
):
    url_formula_field_filter_proc(
        data_fixture, filter_type_name, test_value, expected_rows
    )
