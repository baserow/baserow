import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_filter_type_registry


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_empty_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Some text"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": ""}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": None}
    )

    # Create an empty filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="empty",
        value="",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only rows with empty values
    assert queryset.count() == 2
    assert row_2 in queryset
    assert row_3 in queryset
    assert row_1 not in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_not_empty_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Some text"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": ""}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": None}
    )

    # Create a not_empty filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="not_empty",
        value="",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only rows with non-empty values
    assert queryset.count() == 1
    assert row_1 in queryset
    assert row_2 not in queryset
    assert row_3 not in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_contains_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Hello world"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Goodbye world"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Test message"}
    )

    # Create a contains filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="contains",
        value="world",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only rows containing "world"
    assert queryset.count() == 2
    assert row_1 in queryset
    assert row_2 in queryset
    assert row_3 not in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_contains_not_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Hello world"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Goodbye world"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Test message"}
    )

    # Create a contains_not filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="contains_not",
        value="world",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only rows not containing "world"
    assert queryset.count() == 1
    assert row_3 in queryset
    assert row_1 not in queryset
    assert row_2 not in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_contains_word_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Hello world"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "worldwide coverage"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Test world"}
    )

    # Create a contains_word filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="contains_word",
        value="world",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only rows containing "world" as a whole word
    assert queryset.count() == 2
    assert row_1 in queryset
    assert row_3 in queryset
    assert row_2 not in queryset  # "worldwide" doesn't contain "world" as whole word


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_equal_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "exact match"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Exact match"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "different"}
    )

    # Create an equal filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="equal",
        value="exact match",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only the exact match (case-sensitive)
    assert queryset.count() == 1
    assert row_1 in queryset
    assert row_2 not in queryset
    assert row_3 not in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_equal_filter_with_numeric_string(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "17"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "170"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "different"}
    )

    # Create an equal filter for "17"
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="equal",
        value="17",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    # Should return only the exact match "17"
    assert queryset.count() == 1
    assert row_1 in queryset
    assert row_2 not in queryset  # "170" is not equal to "17"
    assert row_3 not in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_not_equal_filter(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "exact match"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Exact match"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "different"}
    )

    # Create a not_equal filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="not_equal",
        value="exact match",
    )

    # Apply the filter
    queryset = view_handler.get_queryset(grid_view)

    assert queryset.count() == 2
    assert row_1 not in queryset
    assert row_2 in queryset
    assert row_3 in queryset


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_text_output_supports_length_is_lower_than_filter(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    grid_view = premium_data_fixture.create_grid_view(table=table)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    handler = RowHandler()
    model = table.get_model()

    row_1 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Hi"}
    )
    row_2 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Hello"}
    )
    row_3 = handler.create_row(
        user=user, table=table, values={f"field_{ai_field.id}": "Hello World"}
    )

    # Create a length_is_lower_than filter
    view_handler = ViewHandler()
    view_handler.create_filter(
        user=user,
        view=grid_view,
        field=ai_field,
        type_name="length_is_lower_than",
        value="6",
    )

    # Apply the filter using view_handler.get_queryset() like other working tests
    queryset = view_handler.get_queryset(grid_view)

    # Should return only rows with length < 6
    assert queryset.count() == 2
    assert row_1 in queryset  # length 2
    assert row_2 in queryset  # length 5
    assert row_3 not in queryset  # length 11


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_is_compatible_with_text_filters(premium_data_fixture):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Text",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="text",
        ai_prompt="'test'",
    )

    # Test that the AI field is compatible with text-based filters
    text_filter_types = [
        "empty",
        "not_empty",
        "contains",
        "contains_not",
        "contains_word",
        "doesnt_contain_word",
        "equal",
        "not_equal",
        "length_is_lower_than",
    ]

    for filter_type_name in text_filter_types:
        filter_type = view_filter_type_registry.get(filter_type_name)
        is_compatible = filter_type.field_is_compatible(ai_field)
        assert is_compatible, f"AI field should be compatible with {filter_type_name}"


@pytest.mark.django_db
@pytest.mark.field_ai
def test_ai_field_choice_output_not_compatible_with_text_only_filters(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user()
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.register_fake_generate_ai_type()

    ai_field = premium_data_fixture.create_ai_field(
        table=table,
        order=1,
        name="AI Choice",
        ai_generative_ai_type="test_generative_ai",
        ai_generative_ai_model="test_1",
        ai_output_type="choice",
        ai_prompt="'test'",
    )

    # Test that the AI field with choice output is NOT compatible with
    # text-only filters (like length_is_lower_than)
    filter_type = view_filter_type_registry.get("length_is_lower_than")
    is_compatible = filter_type.field_is_compatible(ai_field)
    assert (
        not is_compatible
    ), "AI field with choice output should NOT be compatible with length_is_lower_than"
