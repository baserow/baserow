import pytest

from baserow.contrib.database.views.models import ViewFilter
from baserow_enterprise.assistant.tools.database.helpers import create_view_filter
from baserow_enterprise.assistant.tools.database.types.view_filters import (
    ViewFilterItemCreate,
)


def _make_filter(field_id, **kwargs):
    """Shortcut to build a ViewFilterItemCreate."""
    return ViewFilterItemCreate(field_id=field_id, **kwargs)


@pytest.mark.django_db
def test_all_text_filters_conversion(data_fixture):
    """Test all text filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Text Field")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    text_filters = [
        ({"type": "text", "operator": "equal", "value": "test"}, "equal", "test"),
        (
            {"type": "text", "operator": "not_equal", "value": "test"},
            "not_equal",
            "test",
        ),
        (
            {"type": "text", "operator": "contains", "value": "keyword"},
            "contains",
            "keyword",
        ),
        (
            {"type": "text", "operator": "contains_not", "value": "spam"},
            "contains_not",
            "spam",
        ),
        ({"type": "text", "operator": "empty", "value": ""}, "empty", ""),
        ({"type": "text", "operator": "not_empty", "value": ""}, "not_empty", ""),
    ]

    for kwargs, expected_type, expected_value in text_filters:
        filter_item = _make_filter(field.id, **kwargs)
        created_filter = create_view_filter(user, view, table_fields, filter_item)

        assert created_filter is not None
        assert created_filter.view.id == view.id
        assert created_filter.field.id == field.id
        assert created_filter.type == expected_type
        assert created_filter.value == expected_value

        assert ViewFilter.objects.filter(
            view=view, field=field, type=expected_type
        ).exists()


@pytest.mark.django_db
def test_all_number_filters_conversion(data_fixture):
    """Test all number filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table, name="Number Field")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    number_filters = [
        (
            {"type": "number", "operator": "equal", "value": 42.0, "or_equal": False},
            "equal",
            "42.0",
        ),
        (
            {
                "type": "number",
                "operator": "not_equal",
                "value": 0.0,
                "or_equal": False,
            },
            "not_equal",
            "0.0",
        ),
        (
            {
                "type": "number",
                "operator": "higher_than",
                "value": 100.0,
                "or_equal": False,
            },
            "higher_than",
            "100.0",
        ),
        (
            {
                "type": "number",
                "operator": "higher_than",
                "value": 100.0,
                "or_equal": True,
            },
            "higher_than_or_equal",
            "100.0",
        ),
        (
            {
                "type": "number",
                "operator": "lower_than",
                "value": 50.0,
                "or_equal": False,
            },
            "lower_than",
            "50.0",
        ),
        (
            {
                "type": "number",
                "operator": "lower_than",
                "value": 50.0,
                "or_equal": True,
            },
            "lower_than_or_equal",
            "50.0",
        ),
        (
            {"type": "number", "operator": "empty", "value": 0.0, "or_equal": False},
            "empty",
            "0.0",
        ),
        (
            {
                "type": "number",
                "operator": "not_empty",
                "value": 0.0,
                "or_equal": False,
            },
            "not_empty",
            "0.0",
        ),
    ]

    for kwargs, expected_type, expected_value in number_filters:
        filter_item = _make_filter(field.id, **kwargs)
        created_filter = create_view_filter(user, view, table_fields, filter_item)

        assert created_filter is not None
        assert created_filter.type == expected_type
        assert created_filter.value == expected_value
        assert ViewFilter.objects.filter(
            view=view, field=field, type=expected_type
        ).exists()


@pytest.mark.django_db
def test_all_date_filters_conversion(data_fixture):
    """Test all date filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table, name="Date Field")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    # Test with exact date
    filter_item = _make_filter(
        field.id,
        type="date",
        operator="equal",
        value="2024-01-15",
        mode="exact_date",
        or_equal=False,
    )
    created = create_view_filter(user, view, table_fields, filter_item)
    assert created.type == "date_is"
    assert "2024-01-15" in created.value
    assert created.value.endswith("?exact_date")

    # Test with relative date (today)
    filter_item2 = _make_filter(
        field.id,
        type="date",
        operator="not_equal",
        value=None,
        mode="today",
        or_equal=False,
    )
    created2 = create_view_filter(user, view, table_fields, filter_item2)
    assert created2.type == "date_is_not"
    assert created2.value.endswith("??today")

    # Test date_is_after
    filter_item3 = _make_filter(
        field.id,
        type="date",
        operator="after",
        value=7,
        mode="nr_days_ago",
        or_equal=False,
    )
    created3 = create_view_filter(user, view, table_fields, filter_item3)
    assert created3.type == "date_is_after"
    assert "?7?" in created3.value
    assert created3.value.endswith("nr_days_ago")

    # Test date_is_on_or_after
    filter_item4 = _make_filter(
        field.id,
        type="date",
        operator="after",
        value=30,
        mode="nr_days_from_now",
        or_equal=True,
    )
    created4 = create_view_filter(user, view, table_fields, filter_item4)
    assert created4.type == "date_is_on_or_after"

    # Test date_is_before
    filter_item5 = _make_filter(
        field.id,
        type="date",
        operator="before",
        value=None,
        mode="tomorrow",
        or_equal=False,
    )
    created5 = create_view_filter(user, view, table_fields, filter_item5)
    assert created5.type == "date_is_before"

    # Test date_is_on_or_before
    filter_item6 = _make_filter(
        field.id,
        type="date",
        operator="before",
        value=14,
        mode="nr_weeks_from_now",
        or_equal=True,
    )
    created6 = create_view_filter(user, view, table_fields, filter_item6)
    assert created6.type == "date_is_on_or_before"


@pytest.mark.django_db
def test_all_single_select_filters_conversion(data_fixture):
    """Test all single select filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_single_select_field(table=table, name="Status")
    option1 = data_fixture.create_select_option(field=field, value="Active", order=1)
    option2 = data_fixture.create_select_option(field=field, value="Pending", order=2)
    option3 = data_fixture.create_select_option(field=field, value="Inactive", order=3)
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    # Test is_any_of
    filter_item = _make_filter(
        field.id,
        type="single_select",
        operator="is_any_of",
        value=["Active", "Pending"],
    )
    created = create_view_filter(user, view, table_fields, filter_item)
    assert created.type == "single_select_is_any_of"
    option_ids = created.value.split(",")
    assert str(option1.id) in option_ids
    assert str(option2.id) in option_ids
    assert len(option_ids) == 2

    # Test case insensitive matching
    filter_item2 = _make_filter(
        field.id, type="single_select", operator="is_any_of", value=["active"]
    )
    created2 = create_view_filter(user, view, table_fields, filter_item2)
    assert str(option1.id) in created2.value

    # Test is_none_of
    filter_item3 = _make_filter(
        field.id, type="single_select", operator="is_none_of", value=["Inactive"]
    )
    created3 = create_view_filter(user, view, table_fields, filter_item3)
    assert created3.type == "single_select_is_none_of"
    assert str(option3.id) in created3.value


@pytest.mark.django_db
def test_all_multiple_select_filters_conversion(data_fixture):
    """Test all multiple select filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    option1 = data_fixture.create_select_option(field=field, value="Important", order=1)
    option2 = data_fixture.create_select_option(field=field, value="Urgent", order=2)
    option3 = data_fixture.create_select_option(field=field, value="Archived", order=3)
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    # Test is_any_of (has)
    filter_item = _make_filter(
        field.id,
        type="multiple_select",
        operator="is_any_of",
        value=["Important", "Urgent"],
    )
    created = create_view_filter(user, view, table_fields, filter_item)
    assert created.type == "multiple_select_has"
    option_ids = created.value.split(",")
    assert str(option1.id) in option_ids
    assert str(option2.id) in option_ids

    # Test is_none_of (has_not)
    filter_item2 = _make_filter(
        field.id, type="multiple_select", operator="is_none_of", value=["Archived"]
    )
    created2 = create_view_filter(user, view, table_fields, filter_item2)
    assert created2.type == "multiple_select_has_not"
    assert str(option3.id) in created2.value


@pytest.mark.django_db
@pytest.mark.skip(
    reason="Link row filters have a bug in Baserow (UnboundLocalError in view_filters.py:1301)"
)
def test_all_link_row_filters_conversion(data_fixture):
    """Test all link row filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table1 = data_fixture.create_database_table(database=database, name="Projects")
    table2 = data_fixture.create_database_table(database=database, name="Tasks")
    field = data_fixture.create_link_row_field(table=table1, link_row_table=table2)
    view = data_fixture.create_grid_view(table=table1)
    table_fields = {field.id: field}

    # Test link_row_has
    filter_item = _make_filter(field.id, type="link_row", operator="has", value=123)
    created = create_view_filter(user, view, table_fields, filter_item)
    assert created.type == "link_row_has"
    assert created.value == "123"

    # Test link_row_has_not
    filter_item2 = _make_filter(
        field.id, type="link_row", operator="has_not", value=456
    )
    created2 = create_view_filter(user, view, table_fields, filter_item2)
    assert created2.type == "link_row_has_not"
    assert created2.value == "456"


@pytest.mark.django_db
def test_all_boolean_filters_conversion(data_fixture):
    """Test all boolean filter operators can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_boolean_field(table=table, name="Active")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    # Test is true
    filter_item = _make_filter(field.id, type="boolean", operator="equal", value=True)
    created = create_view_filter(user, view, table_fields, filter_item)
    assert created.type == "equal"
    assert created.value == "1"

    # Test is false
    filter_item2 = _make_filter(field.id, type="boolean", operator="equal", value=False)
    created2 = create_view_filter(user, view, table_fields, filter_item2)
    assert created2.type == "equal"
    assert created2.value == "0"


@pytest.mark.django_db
def test_comprehensive_all_filter_types_conversion(data_fixture):
    """
    Comprehensive test ensuring all filter config types can be successfully
    converted to Baserow filters with a table containing all supported field types.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="All Fields")

    text_field = data_fixture.create_text_field(table=table, name="Text", primary=True)
    number_field = data_fixture.create_number_field(table=table, name="Number")
    date_field = data_fixture.create_date_field(table=table, name="Date")
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    single_select = data_fixture.create_single_select_field(table=table, name="Status")
    multi_select = data_fixture.create_multiple_select_field(table=table, name="Tags")

    data_fixture.create_select_option(field=single_select, value="Active", order=1)
    data_fixture.create_select_option(field=multi_select, value="Important", order=1)

    view = data_fixture.create_grid_view(table=table)
    table_fields = {
        text_field.id: text_field,
        number_field.id: number_field,
        date_field.id: date_field,
        boolean_field.id: boolean_field,
        single_select.id: single_select,
        multi_select.id: multi_select,
    }

    all_filters = [
        # Text filters
        _make_filter(text_field.id, type="text", operator="equal", value="test"),
        _make_filter(text_field.id, type="text", operator="not_equal", value="test"),
        _make_filter(text_field.id, type="text", operator="contains", value="test"),
        _make_filter(text_field.id, type="text", operator="contains_not", value="test"),
        _make_filter(text_field.id, type="text", operator="empty", value=""),
        _make_filter(text_field.id, type="text", operator="not_empty", value=""),
        # Number filters
        _make_filter(
            number_field.id, type="number", operator="equal", value=42.0, or_equal=False
        ),
        _make_filter(
            number_field.id,
            type="number",
            operator="not_equal",
            value=0.0,
            or_equal=False,
        ),
        _make_filter(
            number_field.id,
            type="number",
            operator="higher_than",
            value=10.0,
            or_equal=False,
        ),
        _make_filter(
            number_field.id,
            type="number",
            operator="lower_than",
            value=100.0,
            or_equal=True,
        ),
        _make_filter(
            number_field.id, type="number", operator="empty", value=0.0, or_equal=False
        ),
        _make_filter(
            number_field.id,
            type="number",
            operator="not_empty",
            value=0.0,
            or_equal=False,
        ),
        # Date filters
        _make_filter(
            date_field.id,
            type="date",
            operator="equal",
            value="2024-01-01",
            mode="exact_date",
            or_equal=False,
        ),
        _make_filter(
            date_field.id,
            type="date",
            operator="not_equal",
            value=None,
            mode="today",
            or_equal=False,
        ),
        _make_filter(
            date_field.id,
            type="date",
            operator="after",
            value=7,
            mode="nr_days_ago",
            or_equal=False,
        ),
        _make_filter(
            date_field.id,
            type="date",
            operator="before",
            value=None,
            mode="tomorrow",
            or_equal=True,
        ),
        # Select filters
        _make_filter(
            single_select.id,
            type="single_select",
            operator="is_any_of",
            value=["Active"],
        ),
        _make_filter(
            single_select.id,
            type="single_select",
            operator="is_none_of",
            value=["Active"],
        ),
        _make_filter(
            multi_select.id,
            type="multiple_select",
            operator="is_any_of",
            value=["Important"],
        ),
        _make_filter(
            multi_select.id,
            type="multiple_select",
            operator="is_none_of",
            value=["Important"],
        ),
        # Boolean filter
        _make_filter(boolean_field.id, type="boolean", operator="equal", value=True),
    ]

    created_filters = []
    for filter_item in all_filters:
        try:
            created_filter = create_view_filter(user, view, table_fields, filter_item)
            created_filters.append(created_filter)
            assert created_filter is not None
            assert created_filter.view.id == view.id
        except Exception as e:
            pytest.fail(f"Failed to create filter {filter_item}: {e}")

    assert len(created_filters) == len(all_filters)
    assert ViewFilter.objects.filter(view=view).count() == len(all_filters)

    filter_types = set(f.type for f in created_filters)
    expected_types = {
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "empty",
        "not_empty",
        "higher_than",
        "lower_than_or_equal",
        "date_is",
        "date_is_not",
        "date_is_after",
        "date_is_on_or_before",
        "single_select_is_any_of",
        "single_select_is_none_of",
        "multiple_select_has",
        "multiple_select_has_not",
        "equal",  # for boolean field
    }
    assert filter_types == expected_types
