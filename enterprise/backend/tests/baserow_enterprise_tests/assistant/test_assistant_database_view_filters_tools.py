import pytest

from baserow.contrib.database.views.models import ViewFilter
from baserow_enterprise.assistant.tools.database.types import (
    BooleanIsViewFilterItemCreate,
    DateAfterViewFilterItemCreate,
    DateBeforeViewFilterItemCreate,
    DateEqualsViewFilterItemCreate,
    DateNotEqualsViewFilterItemCreate,
    LinkRowHasNotViewFilterItemCreate,
    LinkRowHasViewFilterItemCreate,
    MultipleSelectIsAnyViewFilterItemCreate,
    MultipleSelectIsNoneOfNotViewFilterItemCreate,
    NumberEmptyViewFilterItemCreate,
    NumberEqualsViewFilterItemCreate,
    NumberHigherThanViewFilterItemCreate,
    NumberLowerThanViewFilterItemCreate,
    NumberNotEmptyViewFilterItemCreate,
    NumberNotEqualsViewFilterItemCreate,
    SingleSelectIsAnyViewFilterItemCreate,
    SingleSelectIsNoneOfNotViewFilterItemCreate,
    TextContainsViewFilterItemCreate,
    TextEmptyViewFilterItemCreate,
    TextEqualViewFilterItemCreate,
    TextNotContainsViewFilterItemCreate,
    TextNotEmptyViewFilterItemCreate,
    TextNotEqualViewFilterItemCreate,
)
from baserow_enterprise.assistant.tools.database.types.base import Date
from baserow_enterprise.assistant.tools.database.types.view_filters import (
    ViewFilterItemCreate,
)
from baserow_enterprise.assistant.tools.database.utils import create_view_filter


@pytest.mark.django_db
def test_all_text_filters_conversion(data_fixture):
    """Test all text filter types can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Text Field")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    text_filters = [
        (
            TextEqualViewFilterItemCreate(
                field_id=field.id, type="text", operator="equal", value="test"
            ),
            "equal",
            "test",
        ),
        (
            TextNotEqualViewFilterItemCreate(
                field_id=field.id, type="text", operator="not_equal", value="test"
            ),
            "not_equal",
            "test",
        ),
        (
            TextContainsViewFilterItemCreate(
                field_id=field.id, type="text", operator="contains", value="keyword"
            ),
            "contains",
            "keyword",
        ),
        (
            TextNotContainsViewFilterItemCreate(
                field_id=field.id, type="text", operator="contains_not", value="spam"
            ),
            "contains_not",
            "spam",
        ),
        (
            TextEmptyViewFilterItemCreate(
                field_id=field.id, type="text", operator="empty", value=""
            ),
            "empty",
            "",
        ),
        (
            TextNotEmptyViewFilterItemCreate(
                field_id=field.id, type="text", operator="not_empty", value=""
            ),
            "not_empty",
            "",
        ),
    ]

    for filter_create, expected_type, expected_value in text_filters:
        created_filter = create_view_filter(user, view, table_fields, filter_create)

        assert created_filter is not None
        assert created_filter.view.id == view.id
        assert created_filter.field.id == field.id
        assert created_filter.type == expected_type
        assert created_filter.value == expected_value

        # Verify in database
        assert ViewFilter.objects.filter(
            view=view, field=field, type=expected_type
        ).exists()


@pytest.mark.django_db
def test_all_number_filters_conversion(data_fixture):
    """Test all number filter types can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table, name="Number Field")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    number_filters = [
        (
            NumberEqualsViewFilterItemCreate(
                field_id=field.id, type="number", operator="equal", value=42.0
            ),
            "equal",
            "42.0",
        ),
        (
            NumberNotEqualsViewFilterItemCreate(
                field_id=field.id, type="number", operator="not_equal", value=0.0
            ),
            "not_equal",
            "0.0",
        ),
        (
            NumberHigherThanViewFilterItemCreate(
                field_id=field.id,
                type="number",
                operator="higher_than",
                value=100.0,
                or_equal=False,
            ),
            "higher_than",
            "100.0",
        ),
        (
            NumberLowerThanViewFilterItemCreate(
                field_id=field.id,
                type="number",
                operator="lower_than",
                value=50.0,
                or_equal=False,
            ),
            "lower_than",
            "50.0",
        ),
        (
            NumberEmptyViewFilterItemCreate(
                field_id=field.id, type="number", operator="empty", value=0.0
            ),
            "empty",
            "0.0",
        ),
        (
            NumberNotEmptyViewFilterItemCreate(
                field_id=field.id, type="number", operator="not_empty", value=0.0
            ),
            "not_empty",
            "0.0",
        ),
    ]

    for filter_create, expected_type, expected_value in number_filters:
        created_filter = create_view_filter(user, view, table_fields, filter_create)

        assert created_filter is not None
        assert created_filter.type == expected_type
        assert created_filter.value == expected_value
        assert ViewFilter.objects.filter(
            view=view, field=field, type=expected_type
        ).exists()


@pytest.mark.django_db
def test_all_date_filters_conversion(data_fixture):
    """Test all date filter types can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table, name="Date Field")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    # Test with exact date
    date_filter = DateEqualsViewFilterItemCreate(
        field_id=field.id,
        type="date",
        operator="equal",
        value=Date(year=2024, month=1, day=15),
        mode="exact_date",
    )
    created_filter = create_view_filter(user, view, table_fields, date_filter)
    assert created_filter.type == "date_is"
    assert "2024-01-15" in created_filter.value
    assert created_filter.value.endswith("?exact_date")

    # Test with relative date (today)
    date_filter2 = DateNotEqualsViewFilterItemCreate(
        field_id=field.id, type="date", operator="not_equal", value=None, mode="today"
    )
    created_filter2 = create_view_filter(user, view, table_fields, date_filter2)
    assert created_filter2.type == "date_is_not"
    assert created_filter2.value.endswith("??today")

    # Test date_is_after
    date_filter3 = DateAfterViewFilterItemCreate(
        field_id=field.id,
        type="date",
        operator="after",
        value=7,
        mode="nr_days_ago",
        or_equal=False,
    )
    created_filter3 = create_view_filter(user, view, table_fields, date_filter3)
    assert created_filter3.type == "date_is_after"
    assert "?7?" in created_filter3.value
    assert created_filter3.value.endswith("nr_days_ago")

    # Test date_is_on_or_after
    date_filter4 = DateAfterViewFilterItemCreate(
        field_id=field.id,
        type="date",
        operator="after",
        value=30,
        mode="nr_days_from_now",
        or_equal=True,
    )
    created_filter4 = create_view_filter(user, view, table_fields, date_filter4)
    assert created_filter4.type == "date_is_on_or_after"

    # Test date_is_before
    date_filter5 = DateBeforeViewFilterItemCreate(
        field_id=field.id,
        type="date",
        operator="before",
        value=None,
        mode="tomorrow",
        or_equal=False,
    )
    created_filter5 = create_view_filter(user, view, table_fields, date_filter5)
    assert created_filter5.type == "date_is_before"

    # Test date_is_on_or_before
    date_filter6 = DateBeforeViewFilterItemCreate(
        field_id=field.id,
        type="date",
        operator="before",
        value=14,
        mode="nr_weeks_from_now",
        or_equal=True,
    )
    created_filter6 = create_view_filter(user, view, table_fields, date_filter6)
    assert created_filter6.type == "date_is_on_or_before"


@pytest.mark.django_db
def test_all_single_select_filters_conversion(data_fixture):
    """Test all single select filter types can be converted to Baserow filters."""

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
    filter_create = SingleSelectIsAnyViewFilterItemCreate(
        field_id=field.id,
        type="single_select",
        operator="is_any_of",
        value=["Active", "Pending"],
    )
    created_filter = create_view_filter(user, view, table_fields, filter_create)
    assert created_filter.type == "single_select_is_any_of"
    # Value should contain option IDs
    option_ids = created_filter.value.split(",")
    assert str(option1.id) in option_ids
    assert str(option2.id) in option_ids
    assert len(option_ids) == 2

    # Test case insensitive matching
    filter_create2 = SingleSelectIsAnyViewFilterItemCreate(
        field_id=field.id,
        type="single_select",
        operator="is_any_of",
        value=["active"],  # lowercase
    )
    created_filter2 = create_view_filter(user, view, table_fields, filter_create2)
    assert str(option1.id) in created_filter2.value

    # Test is_none_of
    filter_create3 = SingleSelectIsNoneOfNotViewFilterItemCreate(
        field_id=field.id,
        type="single_select",
        operator="is_none_of",
        value=["Inactive"],
    )
    created_filter3 = create_view_filter(user, view, table_fields, filter_create3)
    assert created_filter3.type == "single_select_is_none_of"
    assert str(option3.id) in created_filter3.value


@pytest.mark.django_db
def test_all_multiple_select_filters_conversion(data_fixture):
    """Test all multiple select filter types can be converted to Baserow filters."""

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
    filter_create = MultipleSelectIsAnyViewFilterItemCreate(
        field_id=field.id,
        type="multiple_select",
        operator="is_any_of",
        value=["Important", "Urgent"],
    )
    created_filter = create_view_filter(user, view, table_fields, filter_create)
    assert created_filter.type == "multiple_select_has"
    option_ids = created_filter.value.split(",")
    assert str(option1.id) in option_ids
    assert str(option2.id) in option_ids

    # Test is_none_of (has_not)
    filter_create2 = MultipleSelectIsNoneOfNotViewFilterItemCreate(
        field_id=field.id,
        type="multiple_select",
        operator="is_none_of",
        value=["Archived"],
    )
    created_filter2 = create_view_filter(user, view, table_fields, filter_create2)
    assert created_filter2.type == "multiple_select_has_not"
    assert str(option3.id) in created_filter2.value


@pytest.mark.django_db
@pytest.mark.skip(
    reason="Link row filters have a bug in Baserow (UnboundLocalError in view_filters.py:1301)"
)
def test_all_link_row_filters_conversion(data_fixture):
    """Test all link row filter types can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table1 = data_fixture.create_database_table(database=database, name="Projects")
    table2 = data_fixture.create_database_table(database=database, name="Tasks")
    field = data_fixture.create_link_row_field(table=table1, link_row_table=table2)
    view = data_fixture.create_grid_view(table=table1)
    table_fields = {field.id: field}

    # Test link_row_has
    filter_create = LinkRowHasViewFilterItemCreate(
        field_id=field.id, type="link_row", operator="has", value=123
    )
    created_filter = create_view_filter(user, view, table_fields, filter_create)
    assert created_filter.type == "link_row_has"
    assert created_filter.value == "123"

    # Test link_row_has_not
    filter_create2 = LinkRowHasNotViewFilterItemCreate(
        field_id=field.id, type="link_row", operator="has_not", value=456
    )
    created_filter2 = create_view_filter(user, view, table_fields, filter_create2)
    assert created_filter2.type == "link_row_has_not"
    assert created_filter2.value == "456"


@pytest.mark.django_db
def test_all_boolean_filters_conversion(data_fixture):
    """Test all boolean filter types can be converted to Baserow filters."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_boolean_field(table=table, name="Active")
    view = data_fixture.create_grid_view(table=table)
    table_fields = {field.id: field}

    # Test is true
    filter_create = BooleanIsViewFilterItemCreate(
        field_id=field.id, type="boolean", operator="is", value=True
    )
    created_filter = create_view_filter(user, view, table_fields, filter_create)
    assert created_filter.type == "boolean"
    assert created_filter.value == "1"

    # Test is false
    filter_create2 = BooleanIsViewFilterItemCreate(
        field_id=field.id, type="boolean", operator="is", value=False
    )
    created_filter2 = create_view_filter(user, view, table_fields, filter_create2)
    assert created_filter2.type == "boolean"
    assert created_filter2.value == "0"


def get_all_concrete_filter_classes():
    """
    Recursively find all concrete ViewFilterItemCreate subclasses. Concrete classes are
    those that have specific operators and are meant to be instantiated.
    """

    def get_all_subclasses(cls):
        all_subclasses = []
        for subclass in cls.__subclasses__():
            all_subclasses.append(subclass)
            all_subclasses.extend(get_all_subclasses(subclass))
        return all_subclasses

    all_subclasses = get_all_subclasses(ViewFilterItemCreate)

    # Filter to only concrete classes (those with specific operators defined as Literal)
    # These are the classes that end with "Create" and have a specific operator
    concrete_classes = []
    for cls in all_subclasses:
        # Check if this class defines a specific operator (has Literal type annotation)
        if hasattr(cls, "__annotations__") and "operator" in cls.__annotations__:
            annotation = cls.__annotations__["operator"]
            # Check if it's a Literal type (concrete operator)
            if hasattr(annotation, "__origin__") or "Literal" in str(annotation):
                concrete_classes.append(cls)

    return concrete_classes


def test_filter_class_discovery():
    """
    Test that the filter class discovery mechanism works correctly. This ensures our
    introspection logic properly identifies concrete filter classes.
    """

    all_concrete_classes = get_all_concrete_filter_classes()

    # Verify we found a reasonable number of filter classes
    # As of now, there should be at least 20+ concrete filter classes
    assert len(all_concrete_classes) >= 20, (
        f"Expected at least 20 concrete filter classes, found {len(all_concrete_classes)}. "
        f"Classes found: {[cls.__name__ for cls in all_concrete_classes]}"
    )

    # Verify that known concrete classes are discovered
    class_names = {cls.__name__ for cls in all_concrete_classes}
    expected_classes = {
        "TextEqualViewFilterItemCreate",
        "NumberEqualsViewFilterItemCreate",
        "DateEqualsViewFilterItemCreate",
        "BooleanIsViewFilterItemCreate",
        "LinkRowHasViewFilterItemCreate",
        "SingleSelectIsAnyViewFilterItemCreate",
        "MultipleSelectIsAnyViewFilterItemCreate",
    }

    missing = expected_classes - class_names
    assert not missing, f"Expected classes not found: {missing}"

    # Verify that base/intermediate classes are NOT included
    excluded_classes = {
        "ViewFilterItemCreate",
        "TextViewFilterItemCreate",
        "NumberViewFilterItemCreate",
        "DateViewFilterItemCreate",
    }

    found_excluded = excluded_classes & class_names
    assert (
        not found_excluded
    ), f"Base/intermediate classes should not be included: {found_excluded}"


@pytest.mark.django_db
def test_comprehensive_all_filter_types_conversion(data_fixture):
    """
    Comprehensive test ensuring ALL filter types can be successfully converted to
    Baserow filters with a table containing all supported field types.
    """

    # Setup
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="All Fields")

    # Create all field types
    text_field = data_fixture.create_text_field(table=table, name="Text", primary=True)
    number_field = data_fixture.create_number_field(table=table, name="Number")
    date_field = data_fixture.create_date_field(table=table, name="Date")
    boolean_field = data_fixture.create_boolean_field(table=table, name="Boolean")
    single_select = data_fixture.create_single_select_field(table=table, name="Status")
    multi_select = data_fixture.create_multiple_select_field(table=table, name="Tags")

    linked_table = data_fixture.create_database_table(database=database, name="Linked")
    data_fixture.create_text_field(table=linked_table, name="Linked Text", primary=True)
    link_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )

    data_fixture.create_select_option(field=single_select, value="Active", order=1)
    data_fixture.create_select_option(field=multi_select, value="Important", order=1)

    # Create view and table_fields dict
    view = data_fixture.create_grid_view(table=table)
    table_fields = {
        text_field.id: text_field,
        number_field.id: number_field,
        date_field.id: date_field,
        boolean_field.id: boolean_field,
        single_select.id: single_select,
        multi_select.id: multi_select,
        link_field.id: link_field,
    }

    # List of all filter types to test
    all_filters = [
        # Text filters
        TextEqualViewFilterItemCreate(
            field_id=text_field.id, type="text", operator="equal", value="test"
        ),
        TextNotEqualViewFilterItemCreate(
            field_id=text_field.id, type="text", operator="not_equal", value="test"
        ),
        TextContainsViewFilterItemCreate(
            field_id=text_field.id, type="text", operator="contains", value="test"
        ),
        TextNotContainsViewFilterItemCreate(
            field_id=text_field.id, type="text", operator="contains_not", value="test"
        ),
        TextEmptyViewFilterItemCreate(
            field_id=text_field.id, type="text", operator="empty", value=""
        ),
        TextNotEmptyViewFilterItemCreate(
            field_id=text_field.id, type="text", operator="not_empty", value=""
        ),
        # Number filters
        NumberEqualsViewFilterItemCreate(
            field_id=number_field.id, type="number", operator="equal", value=42.0
        ),
        NumberNotEqualsViewFilterItemCreate(
            field_id=number_field.id, type="number", operator="not_equal", value=0.0
        ),
        NumberHigherThanViewFilterItemCreate(
            field_id=number_field.id,
            type="number",
            operator="higher_than",
            value=10.0,
            or_equal=False,
        ),
        NumberLowerThanViewFilterItemCreate(
            field_id=number_field.id,
            type="number",
            operator="lower_than",
            value=100.0,
            or_equal=True,
        ),
        NumberEmptyViewFilterItemCreate(
            field_id=number_field.id, type="number", operator="empty", value=0.0
        ),
        NumberNotEmptyViewFilterItemCreate(
            field_id=number_field.id, type="number", operator="not_empty", value=0.0
        ),
        # Date filters
        DateEqualsViewFilterItemCreate(
            field_id=date_field.id,
            type="date",
            operator="equal",
            value=Date(year=2024, month=1, day=1),
            mode="exact_date",
        ),
        DateNotEqualsViewFilterItemCreate(
            field_id=date_field.id,
            type="date",
            operator="not_equal",
            value=None,
            mode="today",
        ),
        DateAfterViewFilterItemCreate(
            field_id=date_field.id,
            type="date",
            operator="after",
            value=7,
            mode="nr_days_ago",
            or_equal=False,
        ),
        DateBeforeViewFilterItemCreate(
            field_id=date_field.id,
            type="date",
            operator="before",
            value=None,
            mode="tomorrow",
            or_equal=True,
        ),
        # Select filters
        SingleSelectIsAnyViewFilterItemCreate(
            field_id=single_select.id,
            type="single_select",
            operator="is_any_of",
            value=["Active"],
        ),
        SingleSelectIsNoneOfNotViewFilterItemCreate(
            field_id=single_select.id,
            type="single_select",
            operator="is_none_of",
            value=["Active"],
        ),
        MultipleSelectIsAnyViewFilterItemCreate(
            field_id=multi_select.id,
            type="multiple_select",
            operator="is_any_of",
            value=["Important"],
        ),
        MultipleSelectIsNoneOfNotViewFilterItemCreate(
            field_id=multi_select.id,
            type="multiple_select",
            operator="is_none_of",
            value=["Important"],
        ),
        # Link row filters
        LinkRowHasViewFilterItemCreate(
            field_id=link_field.id, type="link_row", operator="has", value=1
        ),
        LinkRowHasNotViewFilterItemCreate(
            field_id=link_field.id, type="link_row", operator="has_not", value=2
        ),
        # Boolean filter
        BooleanIsViewFilterItemCreate(
            field_id=boolean_field.id, type="boolean", operator="is", value=True
        ),
    ]

    # Test that all filters can be created successfully
    created_filters = []
    for filter_item in all_filters:
        try:
            created_filter = create_view_filter(user, view, table_fields, filter_item)
            created_filters.append(created_filter)
            assert created_filter is not None
            assert created_filter.view.id == view.id
        except Exception as e:
            pytest.fail(f"Failed to create filter {filter_item}: {e}")

    # Verify all filters were created in the database
    assert len(created_filters) == len(all_filters)
    assert ViewFilter.objects.filter(view=view).count() == len(all_filters)

    # Verify each filter type is represented
    filter_types = set(f.type for f in created_filters)
    expected_types = {
        "equal",
        "not_equal",
        "contains",
        "contains_not",
        "empty",
        "not_empty",
        "higher_than",
        "lower_than",
        "date_is",
        "date_is_not",
        "date_is_after",
        "date_is_on_or_before",
        "single_select_is_any_of",
        "single_select_is_none_of",
        "multiple_select_has",
        "multiple_select_has_not",
        "link_row_has",
        "link_row_has_not",
        "boolean",
    }
    assert filter_types == expected_types

    # CRITICAL CHECK: Ensure all concrete filter classes are tested
    all_concrete_classes = get_all_concrete_filter_classes()
    tested_classes = {type(filter_item) for filter_item in all_filters}

    missing_classes = set(all_concrete_classes) - tested_classes
    if missing_classes:
        missing_names = [cls.__name__ for cls in missing_classes]
        pytest.fail(
            f"The following filter classes are not tested: {', '.join(missing_names)}. "
            f"Please add test instances for these classes to the all_filters list."
        )

    # Ensure we're not testing non-existent classes
    extra_classes = tested_classes - set(all_concrete_classes)
    if extra_classes:
        extra_names = [cls.__name__ for cls in extra_classes]
        pytest.fail(
            f"The following classes in the test don't exist as concrete filter classes: "
            f"{', '.join(extra_names)}. Please remove them from the test."
        )
