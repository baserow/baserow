from django.http import HttpRequest

import pytest

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.formula import BaserowFormulaObject, resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry

ROWS = [
    [
        "Cherry",  # fruit
        "Cherry",  # fruit duplicate
        "Strawberry",  # fruit alternate
        9.5,  # rating
        3.5,  # weight
        3.5,  # weight duplicate
        4.98,  # weight alternate
        "2025-11-12T21:22:23Z",  # date
        "2025-11-12T21:22:23Z",  # date duplicate
        "2025-11-13T19:15:56Z",  # date alternate
        True,  # tasty
        True,  # tasty duplicate
        False,  # tasty alternate
        4,  # even number
        3,  # odd number
        "DD-MMM-YYYY HH:mm:ss",  # Date format
    ],
    [
        "Durian",
        "Durian",
        "Banana",
        2,
        8,
        8,
        84.597,
        "2025-11-13T06:11:59Z",
        "2025-11-13T06:11:59Z",
        "2025-11-14T14:09:42Z",
        False,
        False,
        True,
        6,
        7,
        "HH:mm:ss",  # Time format
    ],
]

TEST_CASES_STRINGS = [
    # formula type, data source type, list rows ID, expected
    ("upper", "list_rows", 0, "CHERRY,DURIAN"),
    ("upper", "list_rows_item", 0, "CHERRY"),
    ("upper", "get_row", None, "CHERRY"),
    ("lower", "list_rows", 0, "cherry,durian"),
    ("lower", "list_rows_item", 0, "cherry"),
    ("lower", "get_row", None, "cherry"),
    ("capitalize", "list_rows", 0, "Cherry,durian"),
    ("capitalize", "list_rows_item", 0, "Cherry"),
    ("capitalize", "get_row", None, "Cherry"),
]

TEST_CASES_ARITHMETIC = [
    # operator, expected
    ("+", 13),
    ("-", 6.0),
    ("*", 33.25),
    ("/", 2.7142857142857144),
]

# date formulas operate on "2025-11-12T21:22:23Z"
TEST_CASES_DATE = [
    ("day", 12),
    ("month", 11),
    ("year", 2025),
    ("hour", 21),
    ("minute", 22),
    ("second", 23),
]

TEST_CASES_COMAPRISON = [
    # Text
    ("equal", 0, 1, True),
    ("equal", 0, 2, False),
    ("not_equal", 0, 1, False),
    ("not_equal", 0, 2, True),
    # Number
    ("equal", 4, 5, True),
    ("equal", 4, 6, False),
    ("not_equal", 4, 5, False),
    ("not_equal", 4, 6, True),
    # Date
    ("equal", 7, 8, True),
    ("equal", 7, 9, False),
    ("not_equal", 7, 8, False),
    ("not_equal", 7, 9, True),
    # Boolean
    ("equal", 10, 11, True),
    ("equal", 10, 12, False),
    ("not_equal", 10, 11, False),
    ("not_equal", 10, 12, True),
]

TEST_CASES_BOOLEAN = [
    # formula_name, column, expected
    ("is_even", 13, True),
    ("is_even", 14, False),
    ("is_odd", 13, False),
    ("is_odd", 14, True),
]

TEST_CASES_COMAPRISON_OPERATOR = [
    # Columns: 10 = True, 11 = True, 12 = False
    ("&&", 10, 11, True),
    ("&&", 10, 12, False),
    ("||", 10, 11, True),
    ("||", 10, 12, True),
    ("||", 12, 12, False),
    ("=", 10, 11, True),
    ("=", 10, 12, False),
    # Number columns: 3 = 9.5, 4 = 3.5
    (">", 3, 4, True),
    (">", 4, 3, False),
    (">=", 3, 4, True),
    (">=", 4, 3, False),
    ("<", 3, 4, False),
    ("<", 4, 3, True),
    ("<=", 3, 4, False),
    ("<=", 4, 3, True),
    # Text columns: 1 = Cherry, 2 = Strawberry
    (">", 1, 2, False),
    (">", 2, 1, True),
    (">=", 1, 2, False),
    (">=", 2, 1, True),
    ("<", 1, 2, True),
    ("<", 2, 1, False),
    ("<=", 1, 2, True),
    ("<=", 2, 1, False),
]


def create_test_context(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    field_handler = FieldHandler()
    field_fruit = field_handler.create_field(
        user=user, table=table, type_name="text", name="Fruit"
    )
    field_fruit_duplicate = field_handler.create_field(
        user=user, table=table, type_name="text", name="Fruit (duplicate)"
    )
    field_fruit_alternate = field_handler.create_field(
        user=user, table=table, type_name="text", name="Fruit (alternate)"
    )
    field_rating = field_handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="Rating",
        number_decimal_places=2,
    )
    field_weight = field_handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="Weight KGs",
        number_decimal_places=2,
    )
    field_weight_duplicate = field_handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="Weight KGs (duplicate)",
        number_decimal_places=2,
    )
    field_weight_alternate = field_handler.create_field(
        user=user,
        table=table,
        type_name="number",
        name="Weight KGs (alternate)",
        number_decimal_places=2,
    )
    field_harvested = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        name="Harvested",
        date_include_time=True,
    )
    field_harvested_duplicate = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        name="Harvested (duplicate)",
        date_include_time=True,
    )
    field_harvested_alternate = field_handler.create_field(
        user=user,
        table=table,
        type_name="date",
        name="Harvested (alternate)",
        date_include_time=True,
    )
    field_tasty = field_handler.create_field(
        user=user, table=table, type_name="boolean", name="Is Tasty"
    )
    field_tasty_duplicate = field_handler.create_field(
        user=user, table=table, type_name="boolean", name="Is Tasty (duplicate)"
    )
    field_tasty_alternate = field_handler.create_field(
        user=user, table=table, type_name="boolean", name="Is Tasty (alternate)"
    )
    field_even = field_handler.create_field(
        user=user, table=table, type_name="number", name="Even number"
    )
    field_odd = field_handler.create_field(
        user=user, table=table, type_name="number", name="Odd number"
    )
    field_datetime_format = field_handler.create_field(
        user=user, table=table, type_name="text", name="Datetime Format"
    )

    fields = [
        field_fruit,
        field_fruit_duplicate,
        field_fruit_alternate,
        field_rating,
        field_weight,
        field_weight_duplicate,
        field_weight_alternate,
        field_harvested,
        field_harvested_duplicate,
        field_harvested_alternate,
        field_tasty,
        field_tasty_duplicate,
        field_tasty_alternate,
        field_even,
        field_odd,
        field_datetime_format,
    ]

    row_handler = RowHandler()
    rows = [
        row_handler.create_row(
            user=user,
            table=table,
            values={
                fields[0].db_column: row[0],
                fields[1].db_column: row[1],
                fields[2].db_column: row[2],
                fields[3].db_column: row[3],
                fields[4].db_column: row[4],
                fields[5].db_column: row[5],
                fields[6].db_column: row[6],
                fields[7].db_column: row[7],
                fields[8].db_column: row[8],
                fields[9].db_column: row[9],
                fields[10].db_column: row[10],
                fields[11].db_column: row[11],
                fields[12].db_column: row[12],
                fields[13].db_column: row[13],
                fields[14].db_column: row[14],
                fields[15].db_column: row[15],
            },
        )
        for row in ROWS
    ]

    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(builder=builder)
    data_source_list_rows = (
        data_fixture.create_builder_local_baserow_list_rows_data_source(
            page=page, integration=integration, table=table
        )
    )
    data_source_get_row = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page, integration=integration, table=table, row_id=rows[0].id
    )

    return {
        "data_source_list_rows": data_source_list_rows,
        "data_source_get_row": data_source_get_row,
        "page": page,
        "fields": fields,
    }


@pytest.mark.django_db
def test_runtime_formula_if(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    # Cherry
    value_cherry = f"get('data_source.{data_source_get_row.id}.{fields[1].db_column}')"
    # Strawberry
    value_strawberry = (
        f"get('data_source.{data_source_get_row.id}.{fields[2].db_column}')"
    )
    # True
    value_true = f"get('data_source.{data_source_get_row.id}.{fields[11].db_column}')"
    # False
    value_false = f"get('data_source.{data_source_get_row.id}.{fields[12].db_column}')"

    fake_request = HttpRequest()
    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    test_cases = [
        (
            f"if({value_true}, {value_cherry}, {value_strawberry})",
            "Cherry",
        ),
        (
            f"if({value_false}, {value_cherry}, {value_strawberry})",
            "Strawberry",
        ),
    ]

    for item in test_cases:
        value, expected = item
        formula = BaserowFormulaObject.create(value)

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{value} expected to resolve to {expected} " f"but got {result}"
        )


@pytest.mark.django_db
def test_runtime_formula_get_property(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    # Cherry
    key = f"get('data_source.{data_source_get_row.id}.{fields[0].db_column}')"
    object_str = '\'{"Cherry": "Dark Red"}\''
    value = f"get_property({object_str}, {key})"
    formula = BaserowFormulaObject.create(value)

    fake_request = HttpRequest()
    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    result = resolve_formula(
        formula, formula_runtime_function_registry, dispatch_context
    )
    expected = "Dark Red"
    assert result == expected, (
        f"{value} expected to resolve to {expected} " f"but got {result}"
    )


@pytest.mark.django_db
def test_runtime_formula_datetime_format(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    date_str = f"get('data_source.{data_source_get_row.id}.{fields[7].db_column}')"
    date_format = f"get('data_source.{data_source_get_row.id}.{fields[15].db_column}')"
    value = f"datetime_format({date_str}, {date_format})"
    formula = BaserowFormulaObject.create(value)

    fake_request = HttpRequest()
    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    result = resolve_formula(
        formula, formula_runtime_function_registry, dispatch_context
    )
    expected = "12-Nov-2025 21:22:23"
    assert result == expected, (
        f"{value} expected to resolve to {expected} " f"but got {result}"
    )


@pytest.mark.django_db
def test_runtime_formula_comparison_operator(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    for test_case in TEST_CASES_COMAPRISON_OPERATOR:
        operator, field_a, field_b, expected = test_case

        value_a = (
            f"get('data_source.{data_source_get_row.id}.{fields[field_a].db_column}')"
        )
        value_b = (
            f"get('data_source.{data_source_get_row.id}.{fields[field_b].db_column}')"
        )

        value = f"{value_a} {operator} {value_b}"
        formula = BaserowFormulaObject.create(value)

        fake_request = HttpRequest()
        dispatch_context = BuilderDispatchContext(
            fake_request, page, only_expose_public_allowed_properties=False
        )

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{value} expected to resolve to {expected} " f"but got {result}"
        )


@pytest.mark.django_db
def test_runtime_formula_comparison(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    for test_case in TEST_CASES_COMAPRISON:
        formula_name, field_a, field_b, expected = test_case

        value_a = (
            f"get('data_source.{data_source_get_row.id}.{fields[field_a].db_column}')"
        )
        value_b = (
            f"get('data_source.{data_source_get_row.id}.{fields[field_b].db_column}')"
        )

        value = f"{formula_name}({value_a}, {value_b})"
        formula = BaserowFormulaObject.create(value)

        fake_request = HttpRequest()
        dispatch_context = BuilderDispatchContext(
            fake_request, page, only_expose_public_allowed_properties=False
        )

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{value} expected to resolve to {expected} " f"but got {result}"
        )


@pytest.mark.django_db
def test_runtime_formula_boolean(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    for test_case in TEST_CASES_BOOLEAN:
        formula_name, field_id, expected = test_case

        value = (
            f"get('data_source.{data_source_get_row.id}.{fields[field_id].db_column}')"
        )

        value = f"{formula_name}({value})"
        formula = BaserowFormulaObject.create(value)

        fake_request = HttpRequest()
        dispatch_context = BuilderDispatchContext(
            fake_request, page, only_expose_public_allowed_properties=False
        )

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{value} expected to resolve to {expected} " f"but got {result}"
        )


@pytest.mark.django_db
def test_runtime_formula_date(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    for test_case in TEST_CASES_DATE:
        formula_name, expected = test_case

        value = f"get('data_source.{data_source_get_row.id}.{fields[7].db_column}')"

        value = f"{formula_name}({value})"
        formula = BaserowFormulaObject.create(value)

        fake_request = HttpRequest()
        dispatch_context = BuilderDispatchContext(
            fake_request, page, only_expose_public_allowed_properties=False
        )

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{value} expected to resolve to {expected} " f"but got {result}"
        )


@pytest.mark.django_db
def test_runtime_formula_arithmetic(data_fixture):
    data = create_test_context(data_fixture)
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    for test_case in TEST_CASES_ARITHMETIC:
        operator, expected = test_case

        value_1 = f"get('data_source.{data_source_get_row.id}.{fields[3].db_column}')"
        value_2 = f"get('data_source.{data_source_get_row.id}.{fields[4].db_column}')"

        value = f"{value_1} {operator} {value_2}"
        formula = BaserowFormulaObject.create(value)

        fake_request = HttpRequest()
        dispatch_context = BuilderDispatchContext(
            fake_request, page, only_expose_public_allowed_properties=False
        )

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{value} expected to resolve to {expected} " f"but got {result}"
        )


@pytest.mark.django_db
def test_runtime_formula_strings(data_fixture):
    data = create_test_context(data_fixture)
    data_source_list_rows = data["data_source_list_rows"]
    data_source_get_row = data["data_source_get_row"]
    page = data["page"]
    fields = data["fields"]

    for test_case in TEST_CASES_STRINGS:
        formula_name, data_source_type, field_id, expected = test_case

        if data_source_type == "list_rows":
            value = f"get('data_source.{data_source_list_rows.id}.*.{fields[field_id].db_column}')"
        elif data_source_type == "list_rows_item":
            value = f"get('data_source.{data_source_list_rows.id}.0.{fields[field_id].db_column}')"
        elif data_source_type == "get_row":
            value = f"get('data_source.{data_source_get_row.id}.{fields[0].db_column}')"

        value = f"{formula_name}({value})"
        formula = BaserowFormulaObject.create(value)

        fake_request = HttpRequest()
        dispatch_context = BuilderDispatchContext(
            fake_request, page, only_expose_public_allowed_properties=False
        )

        result = resolve_formula(
            formula, formula_runtime_function_registry, dispatch_context
        )
        assert result == expected, (
            f"{formula_name}() with {data_source_type} expected {expected} "
            f"but got {result}"
        )
