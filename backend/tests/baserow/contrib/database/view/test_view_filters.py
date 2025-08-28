import random
from contextlib import contextmanager
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from django.db.models import Q

import pytest
from freezegun import freeze_time
from pyinstrument import Profiler
from pytest_unordered import unordered

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewFilter
from baserow.contrib.database.views.registries import (
    ViewFilterType,
    view_filter_type_registry,
)
from baserow.contrib.database.views.view_filters import DateMultiStepViewFilterType
from baserow.test_utils.helpers import setup_interesting_test_table
from tests.baserow.contrib.database.utils import (
    date_field_factory,
    datetime_field_factory,
    duration_field_factory,
    email_field_factory,
    file_field_factory,
    long_text_field_factory,
    multiple_collaborators_field_factory,
    multiple_select_field_factory,
    number_field_factory,
    phone_number_field_factory,
    single_select_field_factory,
    text_field_factory,
    url_field_factory,
)

from .date_utils import (
    DATE_MULTI_STEP_OPERATOR_VALID_RESULTS,
    FREEZED_TODAY,
    MNEMONIC_VALUES,
    TEST_MULTI_STEP_DATE_OPERATORS_DATETIMES,
)


@pytest.mark.django_db
def test_can_use_a_callable_in_compatible_field_types(data_fixture):
    class TestViewFilterType(ViewFilterType):
        type = "test"
        compatible_field_types = [lambda field: field.name == "compatible"]

        def get_filter(
            self, field_name, value, model_field, field
        ) -> OptionallyAnnotatedQ:
            return Q()

    not_compatible_field = data_fixture.create_text_field(name="not_compat")
    assert not TestViewFilterType().field_is_compatible(not_compatible_field)

    compatible_field = data_fixture.create_text_field(name="compatible")
    assert TestViewFilterType().field_is_compatible(compatible_field)


@pytest.mark.django_db
def test_can_mix_field_types_and_callables_in_compatible_field_types(data_fixture):
    class TestViewFilterType(ViewFilterType):
        type = "test"
        compatible_field_types = [
            "text",
            lambda field: field.name == "compatible",
        ]

        def get_filter(
            self, field_name, value, model_field, field
        ) -> OptionallyAnnotatedQ:
            return Q()

    not_compatible_field = data_fixture.create_long_text_field(name="not_compat")
    assert not TestViewFilterType().field_is_compatible(not_compatible_field)

    compatible_field = data_fixture.create_text_field(
        name="name doesn't match but type does"
    )
    assert TestViewFilterType().field_is_compatible(compatible_field)


@pytest.mark.django_db
def test_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "Test",
                    f"field_{long_text_field.id}": "Long",
                    f"field_{integer_field.id}": 10,
                    f"field_{decimal_field.id}": 20.20,
                    f"field_{boolean_field.id}": True,
                },
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{integer_field.id}": None,
                    f"field_{decimal_field.id}": None,
                    f"field_{boolean_field.id}": False,
                },
                {
                    f"field_{text_field.id}": "NOT",
                    f"field_{long_text_field.id}": "NOT2",
                    f"field_{integer_field.id}": 99,
                    f"field_{decimal_field.id}": 99.99,
                    f"field_{boolean_field.id}": False,
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="equal", value="Test"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = long_text_field
    view_filter.value = "Long"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = integer_field
    view_filter.value = "10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    # Because the value 'test' cannot be accepted no results will be returned.
    view_filter.field = integer_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = decimal_field
    view_filter.value = "20.20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = boolean_field
    view_filter.value = "1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = boolean_field
    view_filter.value = "0"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = long_text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = integer_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = decimal_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = boolean_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = "nottest"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = formula_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3


@pytest.mark.django_db
def test_not_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "Test",
                    f"field_{long_text_field.id}": "Long",
                    f"field_{integer_field.id}": 10,
                    f"field_{decimal_field.id}": 20.20,
                    f"field_{boolean_field.id}": True,
                },
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{integer_field.id}": None,
                    f"field_{decimal_field.id}": None,
                    f"field_{boolean_field.id}": False,
                },
                {
                    f"field_{text_field.id}": "NOT",
                    f"field_{long_text_field.id}": "NOT2",
                    f"field_{integer_field.id}": 99,
                    f"field_{decimal_field.id}": 99.99,
                    f"field_{boolean_field.id}": False,
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="not_equal", value="Test"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = long_text_field
    view_filter.value = "Long"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = integer_field
    view_filter.value = "10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    # Because the value 'test' cannot be accepted the filter is not applied so it will
    # return all rows.
    view_filter.field = integer_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = decimal_field
    view_filter.value = "20.20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = boolean_field
    view_filter.value = "1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = boolean_field
    view_filter.value = "0"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = long_text_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = integer_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = decimal_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = boolean_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = "nottest"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = formula_field
    view_filter.value = "test"
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = formula_field
    view_filter.value = ""
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3


@pytest.mark.django_db
def test_contains_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    date_field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_format="ISO"
    )
    number_field = data_fixture.create_number_field(
        table=table,
        number_negative=True,
        number_decimal_places=2,
    )
    field_handler = FieldHandler()
    single_select_field = data_fixture.create_single_select_field(table=table)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "CC", "color": "blue"},
            {"value": "DC", "color": "blue"},
        ],
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="AC", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="BC", color="red"
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="CE", color="green"
    )
    option_d = data_fixture.create_select_option(
        field=multiple_select_field, value="DE", color="yellow"
    )
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row, _, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "My name is John Doe.",
                    f"field_{long_text_field.id}": "Long text that is not empty.",
                    f"field_{date_field.id}": "2020-02-01 01:23",
                    f"field_{number_field.id}": "98989898",
                    f"field_{single_select_field.id}": option_a,
                    f"field_{multiple_select_field.id}": [option_c.id, option_d.id],
                },
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{date_field.id}": None,
                    f"field_{number_field.id}": None,
                    f"field_{single_select_field.id}": None,
                },
                {
                    f"field_{text_field.id}": "This is a test field.",
                    f"field_{long_text_field.id}": "This text is a bit longer, but it also "
                    "contains.\n A multiline approach.",
                    f"field_{date_field.id}": "0001-01-02 00:12",
                    f"field_{number_field.id}": "10000",
                    f"field_{single_select_field.id}": option_b,
                    f"field_{multiple_select_field.id}": [option_c.id],
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains", value="john"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "DOE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "test"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.value = " is "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "random"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = long_text_field
    view_filter.value = "multiLINE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = date_field
    view_filter.value = "2020-02-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_field
    view_filter.value = "01/02/2020"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = number_field
    view_filter.value = "98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = number_field
    view_filter.value = "0" + str(row.id)
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = number_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = date_field
    view_filter.value = "00:12"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = single_select_field
    view_filter.value = "A"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = single_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "D"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = formula_field
    view_filter.value = "tes"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = formula_field
    view_filter.value = "xx"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_contains_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    date_field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_format="ISO"
    )
    number_field = data_fixture.create_number_field(
        table=table,
        number_negative=True,
        number_decimal_places=2,
    )
    single_select_field = data_fixture.create_single_select_field(table=table)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="AC", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="BC", color="red"
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="CE", color="green"
    )
    option_d = data_fixture.create_select_option(
        field=multiple_select_field, value="DE", color="yellow"
    )
    formula_field = data_fixture.create_formula_field(table=table, formula="'test'")

    handler = ViewHandler()
    model = table.get_model()

    row, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "My name is John Doe.",
                    f"field_{long_text_field.id}": "Long text that is not empty.",
                    f"field_{date_field.id}": "2020-02-01 01:23",
                    f"field_{number_field.id}": "98989898",
                    f"field_{single_select_field.id}": option_a,
                    f"field_{multiple_select_field.id}": [option_c.id, option_d.id],
                },
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{date_field.id}": None,
                    f"field_{number_field.id}": None,
                    f"field_{single_select_field.id}": None,
                },
                {
                    f"field_{text_field.id}": "This is a test field.",
                    f"field_{long_text_field.id}": "This text is a bit longer, but it also "
                    "contains.\n A multiline approach.",
                    f"field_{date_field.id}": "0001-01-02 00:12",
                    f"field_{number_field.id}": "10000",
                    f"field_{single_select_field.id}": option_b,
                    f"field_{multiple_select_field.id}": [option_d.id],
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains_not", value="john"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "DOE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "test"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.value = " is "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "random"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = long_text_field
    view_filter.value = "multiLINE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.field = date_field
    view_filter.value = "2020-02-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = date_field
    view_filter.value = "01/02/2020"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = number_field
    view_filter.value = "98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = number_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = date_field
    view_filter.value = "00:12"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id not in ids

    view_filter.field = single_select_field
    view_filter.value = "A"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = single_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "D"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = multiple_select_field
    view_filter.value = "C"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.field = formula_field
    view_filter.value = "tes"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = formula_field
    view_filter.value = "xx"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3


@pytest.mark.django_db
def test_contains_word_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    url_field = data_fixture.create_url_field(table=table)
    email_field = data_fixture.create_email_field(table=table)
    field_handler = FieldHandler()
    single_select_field = data_fixture.create_single_select_field(table=table)
    formula_field = data_fixture.create_formula_field(
        table=table,
        name="formula",
        formula=f"field('{text_field.name}')",  # mimic the text field as it is, just to test the filter
        formula_type="text",
    )
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "CC", "color": "blue"},
            {"value": "DC", "color": "blue"},
        ],
    )

    option_a = data_fixture.create_select_option(
        field=single_select_field, value="AC", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="BC", color="red"
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="CE", color="green"
    )
    option_d = data_fixture.create_select_option(
        field=multiple_select_field, value="DE", color="yellow"
    )

    handler = ViewHandler()
    model = table.get_model()

    row, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "My name is John Doe.",
                    f"field_{long_text_field.id}": "Long text that is not empty, but also not multilined.",
                    f"field_{url_field.id}": "https://www.example.com",
                    f"field_{email_field.id}": "test.user@example.com",
                    f"field_{single_select_field.id}": option_a,
                    f"field_{multiple_select_field.id}": [option_c.id, option_d.id],
                },
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{url_field.id}": "",
                    f"field_{email_field.id}": "",
                    f"field_{single_select_field.id}": None,
                },
                {
                    f"field_{text_field.id}": "This is a test field with the word Johny.",
                    f"field_{long_text_field.id}": "This text is a bit longer, but it also "
                    "contains.\n A multiline approach.",
                    f"field_{url_field.id}": "https://www.examplewebsite.com",
                    f"field_{email_field.id}": "test.user@examplewebsite.com",
                    f"field_{single_select_field.id}": option_b,
                    f"field_{multiple_select_field.id}": [option_c.id],
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="contains_word", value="John"
    )
    # check for whole word in text field
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    # check for multiple words in text field
    view_filter.value = "John Doe"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    # check for case insensitive in text field
    view_filter.value = "JOHNY"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "random"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = formula_field
    view_filter.value = "John Doe"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = long_text_field
    view_filter.value = "multiLINE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = url_field
    view_filter.value = "exAmPle"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = url_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = email_field
    view_filter.value = "ExamplE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = email_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "A"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = single_select_field
    view_filter.value = "AC"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = single_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "E"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = multiple_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "DE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    # multiple select field with multiple values does not work
    view_filter.field = multiple_select_field
    view_filter.value = "DE,CE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_doesnt_contain_word_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    url_field = data_fixture.create_url_field(table=table)
    email_field = data_fixture.create_email_field(table=table)
    field_handler = FieldHandler()
    single_select_field = data_fixture.create_single_select_field(table=table)
    formula_field = data_fixture.create_formula_field(
        table=table,
        name="formula",
        formula=f"field('{text_field.name}')",  # mimic the text field as it is, just to test the filter
        formula_type="text",
    )
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        name="Multiple Select",
        type_name="multiple_select",
        select_options=[
            {"value": "CC", "color": "blue"},
            {"value": "DC", "color": "blue"},
        ],
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="AC", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="BC", color="red"
    )
    option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="CE", color="green"
    )
    option_d = data_fixture.create_select_option(
        field=multiple_select_field, value="DE", color="yellow"
    )

    handler = ViewHandler()
    model = table.get_model()

    row, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "My name is John Doe.",
                    f"field_{long_text_field.id}": "Long text that is not empty, but also not multilined.",
                    f"field_{url_field.id}": "https://www.example.com",
                    f"field_{email_field.id}": "test.user@example.com",
                    f"field_{single_select_field.id}": option_a,
                    f"field_{multiple_select_field.id}": [option_c.id, option_d.id],
                },
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{url_field.id}": "",
                    f"field_{email_field.id}": "",
                    f"field_{single_select_field.id}": None,
                },
                {
                    f"field_{text_field.id}": "This is a test field with the word Johny.",
                    f"field_{long_text_field.id}": "This text is a bit longer, but it also "
                    "contains.\n A multiline approach.",
                    f"field_{url_field.id}": "https://www.examplewebsite.com",
                    f"field_{email_field.id}": "test.user@examplewebsite.com",
                    f"field_{single_select_field.id}": option_b,
                    f"field_{multiple_select_field.id}": [option_c.id],
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="doesnt_contain_word", value="John"
    )
    # check for whole word in text field
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    # check for multiple words in text field
    view_filter.value = "John Doe"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    # check for case insensitive in text field
    view_filter.value = "JOHNY"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id not in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.value = "random"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = formula_field
    view_filter.value = "John Doe"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = long_text_field
    view_filter.value = "multiLINE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id not in ids

    view_filter.field = url_field
    view_filter.value = "exAmPle"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = url_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = email_field
    view_filter.value = "ExamplE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = email_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "A"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = single_select_field
    view_filter.value = "AC"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    view_filter.field = single_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    view_filter.field = multiple_select_field
    view_filter.value = "E"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3

    view_filter.field = multiple_select_field
    view_filter.value = "DE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id not in ids

    # multiple select field with multiple values does not work
    view_filter.field = multiple_select_field
    view_filter.value = "DE,CE"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3


@pytest.mark.django_db
def test_boolean_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    boolean_field = data_fixture.create_boolean_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{boolean_field.id}": True,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{boolean_field.id}": False,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=boolean_field, type="boolean", value="TRUE"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "Y"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "on"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "false"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "no"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = "off"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids


@pytest.mark.django_db
def test_higher_than_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    integer_field = data_fixture.create_number_field(table=table, number_negative=True)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=True,
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
        }
    )
    model.objects.create(
        **{
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{integer_field.id}": -10,
            f"field_{decimal_field.id}": -30.33,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=integer_field, type="higher_than", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "9.4444"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "9.8"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    # with an invalid filter value no results are returned
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-5"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "-11"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.value = "-10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "-9.99999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "9.9999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.19999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.20001"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = decimal_field
    view_filter.value = "99.98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.field = decimal_field
    view_filter.value = "1000"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    # with an invalid filter value no results are returned
    view_filter.field = decimal_field
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_higher_than_or_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    integer_field = data_fixture.create_number_field(table=table, number_negative=True)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=True,
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
        }
    )
    model.objects.create(
        **{
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{integer_field.id}": -10,
            f"field_{decimal_field.id}": -30.33,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=integer_field, type="higher_than_or_equal", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert (
        len(ids) == 2
    )  # Only rows with values 10 and 99 are equal to or greater than 1
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2  # Rows with 10 and 99 are equal to or greater than 10
    assert row.id in ids
    assert row_3.id in ids

    view_filter.value = "99"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1  # Only row_3 matches because it's equal to or greater than 99
    assert row_3.id in ids

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0  # No rows match

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "0"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2  # Rows with 10 and 99 are equal to or greater than 0

    view_filter.value = "-10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert (
        len(ids) == 3
    )  # Includes row, row_3, and row_4 because it's equal to or greater than -10

    view_filter.field = decimal_field
    view_filter.value = "20.20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert (
        len(ids) == 2
    )  # Matches row and row_3 with values equal to or greater than 20.20

    view_filter.value = "99.99"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1  # Only row_3 matches

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_lower_than_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    integer_field = data_fixture.create_number_field(table=table, number_negative=True)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=True,
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
        }
    )
    model.objects.create(
        **{
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{integer_field.id}": -10,
            f"field_{decimal_field.id}": -30.33,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=integer_field, type="lower_than", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "9.4444"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "9.8"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    # with an invalid filter value no results are returned
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-5"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "-9"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "-10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-9.99999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "9.9999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.199999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "20.20001"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "99.98"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_4.id in ids

    view_filter.field = decimal_field
    view_filter.value = "1000"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    # with an invalid filter value no results are returned
    view_filter.field = decimal_field
    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_lower_than_or_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    integer_field = data_fixture.create_number_field(table=table, number_negative=True)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=True,
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{integer_field.id}": 10,
            f"field_{decimal_field.id}": 20.20,
        }
    )
    model.objects.create(
        **{
            f"field_{integer_field.id}": None,
            f"field_{decimal_field.id}": None,
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{integer_field.id}": 99,
            f"field_{decimal_field.id}": 99.99,
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{integer_field.id}": -10,
            f"field_{decimal_field.id}": -30.33,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=integer_field, type="lower_than_or_equal", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = "100"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3  # Includes row, row_3, row_4;

    view_filter.value = "-10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1  # Only row_4 matches

    view_filter.value = "9"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1  # Only row_4 matches

    view_filter.field = decimal_field
    view_filter.value = "20.20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2  # Includes row and row_4;


@pytest.mark.django_db
def test_is_even_and_whole_number_filter_type(data_fixture):
    """
    Tests 'is_even_and_whole' number filter type.

    Tests rows of:
    - whole even/odd numbers
    - fraction even/odd numbers
    - 'None' as a number value
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table,
        number_decimal_places=2,
        number_negative=False,
    )

    handler = ViewHandler()
    model = table.get_model()

    first_even_whole_number_row = model.objects.create(
        **{
            f"field_{decimal_field.id}": 2,
        }
    )
    even_fraction_number_row = model.objects.create(
        **{
            f"field_{decimal_field.id}": 2.2,
        }
    )
    odd_whole_number_row = model.objects.create(
        **{
            f"field_{decimal_field.id}": 3.0,
        }
    )
    odd_fraction_number_row = model.objects.create(
        **{
            f"field_{decimal_field.id}": 3.3,
        }
    )
    second_even_whole_number_row = model.objects.create(
        **{
            f"field_{decimal_field.id}": 4.00,
        }
    )
    null_number_row = model.objects.create(
        **{
            f"field_{decimal_field.id}": None,
        }
    )

    # Test with this filter being applied, this should return even AND whole
    # numbers:
    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=decimal_field, type="is_even_and_whole", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert first_even_whole_number_row.id in ids
    assert second_even_whole_number_row.id in ids


@pytest.mark.django_db
def test_date_equal_filter_type_with_timezone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": datetime(
                2023, 3, 3, 0, 0, 0, tzinfo=timezone.utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2019, 1, 1),
            f"field_{date_time_field.id}": datetime(
                2020, 6, 17, 1, 30, 5, tzinfo=timezone.utc
            ),
        }
    )
    model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
            f"field_{date_time_field.id}": datetime(
                2010, 2, 4, 2, 45, 45, tzinfo=timezone.utc
            ),
        }
    )
    FieldHandler().update_field(
        user, date_time_field, date_force_timezone="Europe/Chisinau"
    )
    ViewHandler().create_filter(
        user,
        grid_view,
        date_time_field,
        "date_equal",
        "Europe/Chisinau?2023-03-03 02:00",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids


@pytest.mark.django_db
def test_date_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": datetime(
                2020, 6, 17, 1, 30, 0, tzinfo=timezone.utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2019, 1, 1),
            f"field_{date_time_field.id}": datetime(
                2020, 6, 17, 1, 30, 5, tzinfo=timezone.utc
            ),
        }
    )
    model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
            f"field_{date_time_field.id}": datetime(
                2010, 2, 4, 2, 45, 45, tzinfo=timezone.utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_equal", value="2020-06-17"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_field
    view_filter.value = "2019-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = date_field
    view_filter.value = "2018-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = date_field
    view_filter.value = "2019-01-01 12:00:00"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_time_field
    view_filter.value = " 2020-06-17 01:30:00 "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:05"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_2.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.field = date_time_field
    view_filter.value = "  2020-06-17  "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_time_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4


@pytest.mark.django_db
def test_last_modified_date_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_field_date = data_fixture.create_last_modified_field(
        table=table, date_include_time=False
    )
    last_modified_field_datetime = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/Athens"
    )
    model = table.get_model()

    # 2021-08-04 in Athens
    with freeze_time("2021-08-04 12:00"):
        model.objects.create(**{})

    # 2021-08-05 in Athens
    with freeze_time("2021-08-04 22:01"):
        row_2 = model.objects.create(**{})

    # 2021-08-05 in Athens
    with freeze_time("2021-08-05 00:01"):
        row_3 = model.objects.create(**{})

    handler = ViewHandler()
    model = table.get_model()

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime,
        type="date_equal",
        value="2021-08-05",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert ids == unordered([row_2.id, row_3.id])

    filter.field = last_modified_field_date
    filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert ids == unordered([row_3.id])


@pytest.mark.django_db
def test_last_modified_datetime_equals_days_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_field_date = data_fixture.create_last_modified_field(
        table=table, date_include_time=False
    )
    last_modified_field_datetime = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/Rome"
    )

    model = table.get_model()

    with freeze_time("2023-02-19 12:00"):
        row = model.objects.create(**{})

    with freeze_time("2023-02-19 18:00"):
        row_2 = model.objects.create(**{})

    with freeze_time("2023-02-20 13:00"):
        row_3 = model.objects.create(**{})

    with freeze_time("2023-02-20 22:00"):
        row_4 = model.objects.create(**{})

    with freeze_time("2023-02-20 23:30"):
        # 2023-02-21 0:30 in Europe/Rome
        row_5 = model.objects.create(**{})

    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime,
        type="date_equals_days_ago",
        value="Europe/Rome?{days_ago}".format(days_ago=1),
    )

    with freeze_time("2023-02-21 12:00"):
        ids = apply_filter()
        assert ids == [row_3.id, row_4.id]

        filter.value = "Europe/Rome?{days_ago}".format(days_ago=2)
        filter.save()
        ids = apply_filter()
        assert ids == [row.id, row_2.id]

        filter.value = "Europe/Rome?0"
        filter.save()
        ids = apply_filter()
        assert ids == [row_5.id]

        filter.field = last_modified_field_date
        filter.value = "UTC?0"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 0

        filter.value = "UTC?1"
        filter.save()
        ids = apply_filter()
        assert ids == [row_3.id, row_4.id, row_5.id]

        # an invalid value results in an empty filter
        for invalid_value in ["", "UTC?1?", "UTC?"]:
            filter.value = invalid_value
            filter.save()
            ids = apply_filter()
            assert len(ids) == 5
            for r in [row, row_2, row_3, row_4]:
                assert r.id in ids

        # if `days_ago` value results in a BC date, no results are returned
        max_days_ago = (datetime.utcnow() - datetime(1, 1, 1)).days
        filter.value = f"UTC?{max_days_ago + 1}"
        filter.save()
        ids = apply_filter()
        assert len(ids) == 0


@pytest.mark.django_db
def test_last_modified_date_equals_days_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    test_date = date(2021, 2, 1)

    row = model.objects.create(
        **{
            f"field_{date_field.id}": test_date,
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 1),
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 2),
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )
    row_5 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
        }
    )

    test_datetime = datetime.combine(test_date, datetime.min.time())
    days_ago = (datetime.utcnow() - test_datetime).days

    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=date_field,
        type="date_equals_days_ago",
        value=f"UTC?{days_ago}",
    )

    ids = apply_filter()
    assert len(ids) == 1
    assert row.id in ids

    filter.value = f"?{days_ago + 1}"
    filter.save()
    ids = apply_filter()
    assert len(ids) == 0

    # an invalid value results in an empty filter
    for invalid_value in ["", "UTC?1?", "UTC?"]:
        filter.value = invalid_value
        filter.save()
        ids = apply_filter()
        assert len(ids) == 5
        for r in [row, row_2, row_3, row_4, row_5]:
            assert r.id in ids

    # if `days_ago` value results in a BC date, no results are returned
    max_days_ago = (datetime.utcnow() - datetime(1, 1, 1)).days
    filter.value = f"UTC?{max_days_ago + 1}"
    filter.save()
    ids = apply_filter()
    assert len(ids) == 0


@pytest.mark.django_db
def test_date_equals_months_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table, date_include_time=False)
    handler = ViewHandler()
    model = table.get_model()
    row_jan_1 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 1, 1),
        }
    )
    row_jan_18 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 1, 18),
        }
    )
    row_feb_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 2, 3),
        }
    )
    row_feb_17 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 2, 17),
        }
    )
    row_march_1 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 3, 1),
        }
    )
    row_march_15 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 3, 15),
        }
    )
    row_april_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 4, 2),
        }
    )
    row_none = model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )
    row_old_year = model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
        }
    )

    with freeze_time("2022-03-15 10:00"):
        filter = data_fixture.create_view_filter(
            view=grid_view,
            field=date_field,
            type="date_equals_months_ago",
            value="{months_ago}".format(months_ago=0),
        )
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_march_1, row_march_15]

    with freeze_time("2022-03-15 10:00"):
        filter.value = "UTC?{months_ago}".format(months_ago=1)
        filter.save()
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_feb_3, row_feb_17]

    with freeze_time("2022-03-15 10:00"):
        filter.value = "UTC?{months_ago}".format(months_ago=2)
        filter.save()
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_jan_1, row_jan_18]

    with freeze_time("2022-03-15 10:00"):
        filter.value = "UTC?{months_ago}".format(months_ago=3)
        filter.save()
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == []


@pytest.mark.django_db
def test_datetime_equals_months_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)
    handler = ViewHandler()
    model = table.get_model()
    row_jan_1 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-01 00:00Z"}
    )
    row_jan_18 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-01-18 05:00Z"}
    )
    row_feb_3 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-02-03 23:59Z"}
    )
    row_feb_18 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-02-18 21:59Z"}
    )
    row_march_01 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-03-01 15:15Z"}
    )
    row_march_17 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-03-17 23:59Z"}
    )
    row_april_1 = model.objects.create(
        **{f"field_{datetime_field.id}": "2022-04-01 00:00Z"}
    )
    row_none = model.objects.create(
        **{
            f"field_{datetime_field.id}": None,
        }
    )
    row_old_year = model.objects.create(
        **{f"field_{datetime_field.id}": "2010-01-01 15:15Z"}
    )

    with freeze_time("2022-03-16 10:00"):
        filter = data_fixture.create_view_filter(
            view=grid_view,
            field=datetime_field,
            type="date_equals_months_ago",
            value="{months_ago}".format(months_ago=0),
        )
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_march_01, row_march_17]

    with freeze_time("2022-03-16 10:00"):
        filter.value = "UTC?{months_ago}".format(months_ago=1)
        filter.save()
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_feb_3, row_feb_18]

    with freeze_time("2022-03-16 10:00"):
        filter.value = "UTC?{months_ago}".format(months_ago=2)
        filter.save()
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_jan_1, row_jan_18]

    with freeze_time("2022-03-16 10:00"):
        filter.value = "UTC?{months_ago}".format(months_ago=3)
        filter.save()
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == []


@pytest.mark.django_db
def test_datetime_equals_months_ago_filter_type_timezone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    datetime_field = data_fixture.create_date_field(
        table=table, date_include_time=True, date_force_timezone="Europe/Rome"
    )
    handler = ViewHandler()
    model = table.get_model()
    row_jan_1 = model.objects.create(
        **{
            f"field_{datetime_field.id}": "2022-01-01 00:00+01:00",
        }
    )

    # 2022-02-01 00:00 UTC is 2022-02-01 01:00 Europe/Rome
    with freeze_time("2022-02-01 00:00"):
        filter = data_fixture.create_view_filter(
            view=grid_view,
            field=datetime_field,
            type="date_equals_months_ago",
            value="Europe/Rome?{months_ago}".format(months_ago=1),
        )
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_jan_1]

    # 2022-02-31 23:00 UTC is 2022-02-01 00:00 Europe/Rome
    with freeze_time("2022-01-31 23:00"):
        rows = list(handler.apply_filters(grid_view, model.objects.all()).all())
        assert rows == [row_jan_1]


@pytest.mark.django_db
def test_date_equals_years_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table, date_include_time=False)
    handler = ViewHandler()
    model = table.get_model()
    row_2022 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 1, 1),
        }
    )
    row_2022_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2022, 12, 30),
        }
    )
    row_2021 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 3, 1),
        }
    )
    row_2020 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 3, 15),
        }
    )
    row_none = model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )

    day_in_2022 = "2022-03-31 10:00"

    years_ago = 0
    with freeze_time(day_in_2022):
        filter = data_fixture.create_view_filter(
            view=grid_view,
            field=date_field,
            type="date_equals_years_ago",
            value=f"UTC?{years_ago}",
        )
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 2
        assert row_2022 in rows
        assert row_2022_2 in rows

    years_ago = 1
    with freeze_time(day_in_2022):
        filter.value = f"UTC?{years_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 1
        assert row_2021 in rows

    years_ago = 2
    with freeze_time(day_in_2022):
        filter.value = f"UTC?{years_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 1
        assert row_2020 in rows

    years_ago = 3
    with freeze_time(day_in_2022):
        filter.value = f"UTC?{years_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 0


@pytest.mark.django_db
def test_datetime_equals_years_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)
    handler = ViewHandler()
    model = table.get_model()
    row_2022 = model.objects.create(
        **{
            f"field_{datetime_field.id}": "2022-01-01 00:00",
        }
    )
    row_2022_2 = model.objects.create(
        **{
            f"field_{datetime_field.id}": "2022-02-03 23:59",
        }
    )
    row_2021 = model.objects.create(
        **{
            f"field_{datetime_field.id}": "2021-03-01 15:15",
        }
    )
    row_2020 = model.objects.create(
        **{
            f"field_{datetime_field.id}": "2020-03-31 23:59",
        }
    )
    row_none = model.objects.create(
        **{
            f"field_{datetime_field.id}": None,
        }
    )

    day_in_march = "2022-03-31 10:00"

    months_ago = 0
    with freeze_time(day_in_march):
        filter = data_fixture.create_view_filter(
            view=grid_view,
            field=datetime_field,
            type="date_equals_years_ago",
            value=f"UTC?{months_ago}",
        )
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 2
        assert row_2022 in rows
        assert row_2022_2 in rows

    months_ago = 1
    with freeze_time(day_in_march):
        filter.value = f"UTC?{months_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 1
        assert row_2021 in rows

    months_ago = 2
    with freeze_time(day_in_march):
        filter.value = f"UTC?{months_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 1
        assert row_2020 in rows

    months_ago = 3
    with freeze_time(day_in_march):
        filter.value = f"UTC?{months_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 0


@pytest.mark.django_db
def test_datetime_equals_years_ago_filter_type_timezone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)
    handler = ViewHandler()
    model = table.get_model()
    row_dec = model.objects.create(
        **{
            f"field_{datetime_field.id}": "2021-12-30 00:00",
        }
    )

    day_in_2022 = "2022-01-01 00:00"

    # without timezone shifting the day
    months_ago = 0

    with freeze_time(day_in_2022):
        filter = data_fixture.create_view_filter(
            view=grid_view,
            field=datetime_field,
            type="date_equals_years_ago",
            value=f"UTC?{months_ago}",
        )
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 0

    # with timezone moving the day to january
    with freeze_time(day_in_2022):
        filter.value = f"America/Havana?{months_ago}"
        filter.save()
        rows = handler.apply_filters(grid_view, model.objects.all()).all()
        assert len(rows) == 1


@pytest.mark.django_db
def test_last_modified_date_equals_today_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)

    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/Berlin"
    )

    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/London"
    )

    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    with freeze_time("2023-08-04 21:59"):
        # 2023-08-04 22:59 in London
        # 2023-08-04 23:59 in Berlin
        row = model.objects.create(**{})

    with freeze_time("2023-08-04 22:01"):
        # 2023-08-04 23:01 in London
        # 2023-08-05 00:01 in Berlin
        row_1 = model.objects.create(**{})

    with freeze_time("2023-08-04 23:01"):
        # 2023-08-05 00:01 in London
        # 2023-08-05 01:01 in Berlin
        row_2 = model.objects.create(**{})

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime_london,
        type="date_equals_today",
        value="Europe/London",
    )

    # 2023-08-04 02:00 in London
    with freeze_time("2023-08-04 01:00"):
        assert apply_filter() == unordered([row.id, row_1.id])

    # 2023-08-04 23:59 in London
    with freeze_time("2023-08-04 22:59"):
        assert apply_filter() == unordered([row.id, row_1.id])

    # 2023-08-05 00:59 in London
    with freeze_time("2023-08-04 23:59"):
        assert apply_filter() == [row_2.id]

    view_filter.field = last_modified_field_datetime_berlin
    view_filter.value = "Europe/Berlin"
    view_filter.save()

    # 2023-08-04 03:00 in Berlin
    with freeze_time("2023-08-04 01:00"):
        assert apply_filter() == [row.id]

    # 2023-08-05 00:59 in Berlin
    with freeze_time("2023-08-04 22:59"):
        assert apply_filter() == unordered([row_1.id, row_2.id])

    # 2023-08-05 01:59 in Berlin
    with freeze_time("2023-08-04 23:59"):
        assert apply_filter() == unordered([row_1.id, row_2.id])


@pytest.mark.django_db
def test_last_modified_month_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)

    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/Berlin"
    )

    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/London"
    )
    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    with freeze_time("2023-08-31 21:59"):
        # 2023-08-31 22:59 in London
        # 2023-08-31 23:59 in Berlin
        row = model.objects.create(**{})

    with freeze_time("2023-08-31 22:01"):
        # 2023-08-31 23:01 in London
        # 2023-09-01 00:01 in Berlin
        row_1 = model.objects.create(**{})

    with freeze_time("2023-08-31 23:01"):
        # 2023-09-01 00:01 in London
        # 2023-09-01 01:01 in Berlin
        row_2 = model.objects.create(**{})

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime_london,
        type="date_equals_month",
        value="Europe/London",
    )

    # 2023-08-31 01:00 in London
    with freeze_time("2023-08-31"):
        assert apply_filter() == unordered([row.id, row_1.id])

    # 2023-09-01 01:00 in London
    with freeze_time("2023-09-01"):
        assert apply_filter() == [row_2.id]

    view_filter.field = last_modified_field_datetime_berlin
    view_filter.value = "Europe/Berlin"
    view_filter.save()

    # 2023-08-31 02:00 in Berlin
    with freeze_time("2023-08-31"):
        assert apply_filter() == [row.id]

    # 2023-09-01 02:00 in Berlin
    with freeze_time("2023-09-01"):
        assert apply_filter() == unordered([row_1.id, row_2.id])


@pytest.mark.django_db
def test_last_modified_year_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)

    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/Berlin"
    )

    last_modified_field_datetime_london = data_fixture.create_last_modified_field(
        table=table, date_include_time=True, date_force_timezone="Europe/London"
    )
    handler = ViewHandler()
    model = table.get_model()

    handler = ViewHandler()
    model = table.get_model()

    def apply_filter():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    with freeze_time("2023-12-31 22:59"):
        # 2023-12-31 22:59 in London
        # 2024-01-01 23:59 in Berlin
        row = model.objects.create(**{})

    with freeze_time("2023-12-31 23:01"):
        # 2024-01-01 23:01 in London
        # 2024-01-01 00:01 in Berlin
        row_1 = model.objects.create(**{})

    with freeze_time("2024-01-01 00:01"):
        # 2024-01-01 00:01 in London
        # 2024-01-01 01:01 in Berlin
        row_2 = model.objects.create(**{})

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_field_datetime_london,
        type="date_equals_year",
        value="Europe/London",
    )

    with freeze_time("2023-12-31"):
        assert apply_filter() == unordered([row.id, row_1.id])

    with freeze_time("2024-01-01"):
        assert apply_filter() == [row_2.id]

    view_filter.field = last_modified_field_datetime_berlin
    view_filter.value = "Europe/Berlin"
    view_filter.save()

    with freeze_time("2023-12-31"):
        assert apply_filter() == [row.id]

    with freeze_time("2024-01-01"):
        assert apply_filter() == unordered([row_1.id, row_2.id])


@pytest.mark.django_db
def test_date_equals_day_week_month_year_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 2, 1),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 1),
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 2),
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 4),
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )
    model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_equals_today", value="UTC"
    )

    with freeze_time("2021-01-01 01:01"):
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row.id not in ids

        view_filter.type = "date_equals_week"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_2.id in ids
        assert row_3.id in ids

        view_filter.type = "date_equals_month"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 3
        assert row_2.id in ids
        assert row_3.id in ids
        assert row_4.id in ids

        view_filter.type = "date_equals_year"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 4
        assert row.id in ids
        assert row_2.id in ids
        assert row_3.id in ids
        assert row_4.id in ids

    view_filter.type = "date_equals_today"
    view_filter.save()

    with freeze_time("2021-01-02 01:01"):
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row_3.id in ids

        view_filter.value = "Etc/UTC+2"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row.id not in ids

        view_filter.value = "NOT_EXISTING_SO_WILL_BE_UTC"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row_3.id in ids


@pytest.mark.django_db
def test_date_before_after_today_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row_1 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 2, 1),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 1),
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 2),
        }
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 1, 4),
        }
    )
    row_5 = model.objects.create(
        **{
            f"field_{date_field.id}": None,
        }
    )
    row_6 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
        }
    )

    row_7 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 12, 31),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_before_today", value="UTC"
    )

    with freeze_time("2021-01-02 01:01"):
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 3
        assert ids == [row_2.id, row_6.id, row_7.id]

        view_filter.type = "date_after_today"
        view_filter.save()

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

        assert len(ids) == 2
        assert ids == [row_1.id, row_4.id]


@pytest.mark.django_db
def test_date_not_equal_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2020, 6, 17),
            f"field_{date_time_field.id}": datetime(
                2020, 6, 17, 1, 30, 0, tzinfo=timezone.utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2019, 1, 1),
            f"field_{date_time_field.id}": datetime(
                2020, 6, 17, 1, 30, 5, tzinfo=timezone.utc
            ),
        }
    )
    row_3 = model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2010, 1, 1),
            f"field_{date_time_field.id}": datetime(
                2010, 2, 4, 2, 45, 45, tzinfo=timezone.utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_not_equal", value="2020-06-17"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_field
    view_filter.value = "2019-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_field
    view_filter.value = "2018-01-01"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_field
    view_filter.value = "2019-01-01 12:00:00"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.field = date_time_field
    view_filter.value = " 2020-06-17 01:30:00 "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2020-06-17 01:30:05"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "Europe/Rome?2020-06-17 02:30:10"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "UTC?2020-06-17"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "  2020-06-17  "
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_4.id in ids

    # If an empty value is provided then the filter will not be applied, so we expect
    # all the rows.
    view_filter.field = date_time_field
    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4


@pytest.mark.django_db
def test_date_before_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 5),
            f"field_{date_time_field.id}": datetime(
                2021, 7, 5, 1, 30, 0, tzinfo=timezone.utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 6),
            f"field_{date_time_field.id}": datetime(
                2021, 7, 6, 1, 30, 5, tzinfo=timezone.utc
            ),
        }
    )
    row_3 = model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 8, 1),
            f"field_{date_time_field.id}": datetime(
                2021, 8, 1, 2, 45, 45, tzinfo=timezone.utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_before", value="2021-07-06"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06 01:20"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06 01:40"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row.id in ids
    assert row_2.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids


@pytest.mark.django_db
def test_date_after_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 5),
            f"field_{date_time_field.id}": datetime(
                2021, 7, 5, 1, 30, 0, tzinfo=timezone.utc
            ),
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 7, 6),
            f"field_{date_time_field.id}": datetime(
                2021, 7, 6, 2, 40, 5, tzinfo=timezone.utc
            ),
        }
    )
    row_3 = model.objects.create(
        **{f"field_{date_field.id}": None, f"field_{date_time_field.id}": None}
    )
    row_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2021, 8, 1),
            f"field_{date_time_field.id}": datetime(
                2021, 8, 1, 2, 45, 45, tzinfo=timezone.utc
            ),
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_after", value="2021-07-06"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-05"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06 01:40"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_4.id in ids

    view_filter.field = date_time_field
    view_filter.value = "2021-07-06 02:41"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_4.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_4.id in ids


@pytest.mark.django_db
def test_empty_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    file_field = data_fixture.create_file_field(table=table)
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(field=single_select_field)
    populated_formula_field = data_fixture.create_formula_field(
        table=table, formula="'test'"
    )
    empty_formula_field = data_fixture.create_formula_field(table=table, formula="''")
    populated_date_interval_formula_field = data_fixture.create_formula_field(
        table=table, formula="date_interval('1 year')"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_2 = data_fixture.create_select_option(field=multiple_select_field)
    option_3 = data_fixture.create_select_option(field=multiple_select_field)

    tmp_table = data_fixture.create_database_table(database=table.database)
    tmp_field = data_fixture.create_text_field(table=tmp_table, primary=True)
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Link row",
        type_name="link_row",
        link_row_table=tmp_table,
    )
    file_a = data_fixture.create_user_file(
        original_name=f"a.txt",
        unique=f"hashed",
        sha256_hash="name",
    )
    file_b = data_fixture.create_user_file(
        original_name=f"b.txt",
        unique=f"other",
        sha256_hash="name",
    )

    tmp_row = RowHandler().create_row(
        user, tmp_table, {f"field_{tmp_field.id}": "Test"}
    )

    handler = ViewHandler()
    model = table.get_model()

    row, row_2, row_3 = (
        RowHandler()
        .create_rows(
            user,
            table,
            [
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{integer_field.id}": None,
                    f"field_{decimal_field.id}": None,
                    f"field_{date_field.id}": None,
                    f"field_{date_time_field.id}": None,
                    f"field_{boolean_field.id}": False,
                    f"field_{file_field.id}": [],
                    f"field_{single_select_field.id}_id": None,
                },
                {
                    f"field_{text_field.id}": "Value",
                    f"field_{long_text_field.id}": "Value",
                    f"field_{integer_field.id}": 10,
                    f"field_{decimal_field.id}": 1022,
                    f"field_{date_field.id}": date(2020, 6, 17),
                    f"field_{date_time_field.id}": datetime(
                        2020, 6, 17, 1, 30, 0, tzinfo=timezone.utc
                    ),
                    f"field_{boolean_field.id}": True,
                    f"field_{file_field.id}": [{"name": file_a.name}],
                    f"field_{single_select_field.id}_id": option_1.id,
                    f"field_{link_row_field.id}": [tmp_row.id],
                    f"field_{multiple_select_field.id}": [option_2.id],
                },
                {
                    f"field_{text_field.id}": "other value",
                    f"field_{long_text_field.id}": " ",
                    f"field_{integer_field.id}": 0,
                    f"field_{decimal_field.id}": 0.00,
                    f"field_{date_field.id}": date(1970, 1, 1),
                    f"field_{date_time_field.id}": datetime(
                        1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc
                    ),
                    f"field_{boolean_field.id}": True,
                    f"field_{file_field.id}": [
                        {"name": file_a.name},
                        {"name": file_b.name},
                    ],
                    f"field_{single_select_field.id}_id": option_1.id,
                    f"field_{link_row_field.id}": [tmp_row.id],
                    f"field_{multiple_select_field.id}": [option_2.id, option_3.id],
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="empty", value=""
    )
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = long_text_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = integer_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = decimal_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = date_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = date_time_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = link_row_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = boolean_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = file_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = single_select_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = multiple_select_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row.id

    view_filter.field = empty_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 3

    view_filter.field = populated_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = populated_date_interval_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0


@pytest.mark.django_db
def test_not_empty_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    integer_field = data_fixture.create_number_field(table=table)
    decimal_field = data_fixture.create_number_field(
        table=table, number_decimal_places=2
    )
    date_field = data_fixture.create_date_field(table=table)
    date_time_field = data_fixture.create_date_field(
        table=table, date_include_time=True
    )
    boolean_field = data_fixture.create_boolean_field(table=table)
    file_field = data_fixture.create_file_field(table=table)
    file_a = data_fixture.create_user_file(
        original_name=f"a.txt",
        unique=f"hashed",
        sha256_hash="name",
    )
    single_select_field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(field=single_select_field)
    populated_formula_field = data_fixture.create_formula_field(
        table=table, formula="'test'"
    )
    empty_formula_field = data_fixture.create_formula_field(table=table, formula="''")
    populated_date_interval_formula_field = data_fixture.create_formula_field(
        table=table, formula="date_interval('1 year')"
    )
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)
    option_2 = data_fixture.create_select_option(field=multiple_select_field)
    option_3 = data_fixture.create_select_option(field=multiple_select_field)

    tmp_table = data_fixture.create_database_table(database=table.database)
    tmp_field = data_fixture.create_text_field(table=tmp_table, primary=True)
    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        name="Link row",
        type_name="link_row",
        link_row_table=tmp_table,
    )
    tmp_row = tmp_table.get_model().objects.create(**{f"field_{tmp_field.id}": "Test"})

    handler = ViewHandler()
    model = table.get_model()

    _, row_2 = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{text_field.id}": "",
                    f"field_{long_text_field.id}": "",
                    f"field_{integer_field.id}": None,
                    f"field_{decimal_field.id}": None,
                    f"field_{date_field.id}": None,
                    f"field_{date_time_field.id}": None,
                    f"field_{boolean_field.id}": False,
                    f"field_{file_field.id}": [],
                    f"field_{single_select_field.id}": None,
                },
                {
                    f"field_{text_field.id}": "Value",
                    f"field_{long_text_field.id}": "Value",
                    f"field_{integer_field.id}": 10,
                    f"field_{decimal_field.id}": 1022,
                    f"field_{date_field.id}": date(2020, 6, 17),
                    f"field_{date_time_field.id}": datetime(
                        2020, 6, 17, 1, 30, 0, tzinfo=timezone.utc
                    ),
                    f"field_{boolean_field.id}": True,
                    f"field_{file_field.id}": [{"name": file_a.name}],
                    f"field_{single_select_field.id}_id": option_1.id,
                    f"field_{link_row_field.id}": [tmp_row.id],
                    f"field_{multiple_select_field.id}": [option_2.id, option_3.id],
                },
            ],
            model=model,
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="not_empty", value=""
    )
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = long_text_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = integer_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = decimal_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = date_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = date_time_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = link_row_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = boolean_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = file_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = single_select_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).get().id == row_2.id

    view_filter.field = empty_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 0

    view_filter.field = populated_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 2

    view_filter.field = populated_date_interval_formula_field
    view_filter.save()
    assert handler.apply_filters(grid_view, model.objects.all()).count() == 2


@pytest.mark.django_db
def test_not_empty_filter_type_for_link_row_table_with_trashed_rows(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, link_a_to_b = data_fixture.create_two_linked_tables(user=user)
    table_a_primary_field = table_a.get_primary_field()
    table_b_primary_field = table_b.get_primary_field()
    grid_view = data_fixture.create_grid_view(table=table_a)

    table_a_model = table_a.get_model()
    table_b_model = table_b.get_model()
    row_b1 = table_b_model.objects.create(**{table_b_primary_field.db_column: "b1"})
    row_a1 = RowHandler().force_create_row(
        user,
        table_a,
        {table_a_primary_field.db_column: "a1", link_a_to_b.db_column: [row_b1.id]},
        model=table_a_model,
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=link_a_to_b, type="not_empty", value=""
    )
    assert (
        handler.apply_filters(grid_view, table_a_model.objects.all()).get().id
        == row_a1.id
    )

    RowHandler().delete_row(user, table_b, row_b1, model=table_b_model)

    assert list(handler.apply_filters(grid_view, table_a_model.objects.all())) == []


@pytest.mark.django_db
def test_filename_contains_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    file_field = data_fixture.create_file_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"field_{file_field.id}": [{"visible_name": "test_file.png"}],
        }
    )
    row_with_multiple_files = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.doc"},
                {"visible_name": "test.txt"},
            ],
        }
    )
    row_with_no_files = model.objects.create(
        **{
            f"field_{file_field.id}": [],
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="filename_contains",
        value="test_file.png",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = ".jpg"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = ".png"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids

    view_filter.value = "test."
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_multiple_files.id in ids

    view_filter.value = ""
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row.id in ids
    assert row_with_multiple_files.id in ids
    assert row_with_no_files.id in ids

    results = model.objects.all().filter_by_fields_object(
        filter_object={
            f"filter__field_{file_field.id}__filename_contains": [".png"],
        },
        filter_type="AND",
    )
    assert len(results) == 1


@pytest.mark.django_db
def test_filename_contains_filter_type_multiple_filters(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    file_field = data_fixture.create_file_field(table=table)
    handler = ViewHandler()
    model = table.get_model()

    row_1 = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.png"},
                {"visible_name": "another.png"},
            ],
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.doc"},
                {"visible_name": "test.txt"},
            ]
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "another.doc"},
            ],
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="filename_contains",
        value="test",
    )

    view_filter2 = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="filename_contains",
        value="another",
    )

    grid_view.filter_type = "AND"
    grid_view.save()

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    grid_view.filter_type = "OR"
    grid_view.save()

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids


@pytest.mark.django_db
def test_has_file_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    file_field = data_fixture.create_file_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row_with_single_image = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_file.jpg", "is_image": True}
            ],
        }
    )
    row_with_single_document = model.objects.create(
        **{
            f"field_{file_field.id}": [{"visible_name": "doc.doc", "is_image": False}],
        }
    )
    row_with_multiple_documents = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.doc", "is_image": False},
                {"visible_name": "test.txt", "is_image": False},
                {"visible_name": "test.doc", "is_image": False},
                {"visible_name": "test.txt", "is_image": False},
            ],
        }
    )
    row_with_multiple_images = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test.jpg", "is_image": True},
                {"visible_name": "test.png", "is_image": True},
            ],
        }
    )
    row_with_single_image_and_multiple_documents = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_doc.doc", "is_image": False},
                {"visible_name": "test_doc.doc", "is_image": False},
                {"visible_name": "test_image.jpg", "is_image": True},
                {"visible_name": "test_doc.doc", "is_image": False},
            ],
        }
    )
    row_with_single_document_and_multiple_images = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "image1.jpg", "is_image": True},
                {"visible_name": "image2.png", "is_image": True},
                {"visible_name": "doc.doc", "is_image": False},
                {"visible_name": "image3.jpg", "is_image": True},
            ],
        }
    )
    model.objects.create(**{f"field_{file_field.id}": []})

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="has_file_type",
        value="",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 7

    view_filter.value = "image"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_with_single_image.id in ids
    assert row_with_multiple_images.id in ids
    assert row_with_single_image_and_multiple_documents.id in ids
    assert row_with_single_document_and_multiple_images.id in ids

    view_filter.value = "document"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_with_single_document.id in ids
    assert row_with_multiple_documents.id in ids
    assert row_with_single_image_and_multiple_documents.id in ids
    assert row_with_single_document_and_multiple_images.id in ids

    data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="has_file_type",
        value="image",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_with_single_image_and_multiple_documents.id in ids
    assert row_with_single_document_and_multiple_images.id in ids


@pytest.mark.django_db
def test_files_lower_than(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    file_field = data_fixture.create_file_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row_without_files = model.objects.create(**{f"field_{file_field.id}": []})
    row_with_one_file = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_file_1.txt", "is_image": False},
            ],
        }
    )
    row_with_two_files = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_file_1.txt", "is_image": False},
                {"visible_name": "test_file_2.txt", "is_image": False},
            ],
        },
    )
    row_with_three_files = model.objects.create(
        **{
            f"field_{file_field.id}": [
                {"visible_name": "test_file_1.txt", "is_image": False},
                {"visible_name": "test_file_2.txt", "is_image": False},
                {"visible_name": "test_file_3.txt", "is_image": False},
            ],
        },
    )

    # There are no rows whose file column has less than 0 files
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=file_field,
        type="files_lower_than",
        value="0",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    # There are two rows whose file column has less than 2 files
    view_filter.value = 2
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_without_files.id in ids
    assert row_with_one_file.id in ids

    # There are three rows whose file column has less than 4 files
    view_filter.value = 4
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_without_files.id in ids
    assert row_with_one_file.id in ids
    assert row_with_two_files.id in ids
    assert row_with_three_files.id in ids

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0


@pytest.mark.django_db
def test_link_row_preload_values(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table, primary=True)
    related_primary_field = data_fixture.create_text_field(
        table=related_table, primary=True
    )
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"",
    )
    assert view_filter.preload_values["display_name"] is None

    view_filter.value = "test"
    view_filter.save()
    assert view_filter.preload_values["display_name"] is None

    view_filter.value = "-1"
    view_filter.save()
    assert view_filter.preload_values["display_name"] is None

    with django_assert_num_queries(4):
        view_filter.value = f"{related_row_1.id}"
        view_filter.save()
        assert view_filter.preload_values["display_name"] == "Related row 1"


@pytest.mark.django_db
def test_link_row_has_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(table=related_table)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    related_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 2",
        },
    )
    related_row_3 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 3",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_row_2.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [related_row_3.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                related_row_1.id,
                related_row_2.id,
                related_row_3.id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "999999999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = f"{related_row_1.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_with_all_relations.id in ids

    # Testing with multiple IDs
    view_filter.value = f"{related_row_1.id},{related_row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{related_row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{related_row_3.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_with_all_relations.id in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"{related_row_1.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_3.id in ids
    assert row_with_all_relations.id in ids


@pytest.mark.django_db
def test_link_row_reference_same_table_has_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=table,
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_0 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [row_0.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [row_0.id, row_1.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [row_2.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                row_0.id,
                row_1.id,
                row_2.id,
                row_3.id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "9999999"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = f"{row_0.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = f"{row_3.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has",
        value=f"{row_1.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_relations.id in ids


@pytest.mark.django_db
def test_link_row_has_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(table=related_table)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    link_row_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    related_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 2",
        },
    )
    related_row_3 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 3",
        },
    )
    related_row_4 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 4",
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_row_2.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [related_row_3.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                related_row_1.id,
                related_row_2.id,
                related_row_3.id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has_not",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = f"{related_row_4.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 5

    view_filter.value = f"{related_row_1.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id not in ids
    assert row_with_all_relations.id not in ids

    view_filter.value = f"{related_row_2.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_2.id not in ids
    assert row_with_all_relations.id not in ids

    view_filter.value = f"{related_row_3.id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_3.id not in ids
    assert row_with_all_relations.id not in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_has_not",
        value=f"{related_row_1.id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids
    assert row_with_all_relations.id not in ids


@pytest.mark.django_db
def test_multiple_select_has_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi Select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )

    row_handler = RowHandler()
    model = table.get_model()

    select_options = multiple_select_field.select_options.all()
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [],
        },
    )

    row_with_all_select_options = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = f"{select_options[0].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_with_all_select_options.id in ids

    view_filter.value = f"{select_options[1].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids

    view_filter.value = f"{select_options[2].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids

    # chaining filters should also work
    view_filter.value = f"{select_options[2].id}"
    view_filter.save()

    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has",
        value=f"{select_options[1].id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_with_all_select_options.id in ids


@pytest.mark.django_db
def test_multiple_select_has_filter_type_export_import():
    view_filter_type = view_filter_type_registry.get("multiple_select_has")
    id_mapping = {"database_field_select_options": {1: 2}}
    assert view_filter_type.get_export_serialized_value("1", {}) == "1"
    assert view_filter_type.set_import_serialized_value("1", id_mapping) == "2"
    assert view_filter_type.set_import_serialized_value("", id_mapping) == ""
    assert view_filter_type.set_import_serialized_value("wrong", id_mapping) == ""


@pytest.mark.django_db
def test_multiple_select_has_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    field_handler = FieldHandler()
    multiple_select_field = field_handler.create_field(
        user=user,
        table=table,
        type_name="multiple_select",
        name="Multi Select",
        select_options=[
            {"value": "Option 1", "color": "blue"},
            {"value": "Option 2", "color": "blue"},
            {"value": "Option 3", "color": "red"},
        ],
    )

    row_handler = RowHandler()
    model = table.get_model()

    select_options = multiple_select_field.select_options.all()
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
            ],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{multiple_select_field.id}": [
                select_options[0].id,
                select_options[1].id,
                select_options[2].id,
            ],
        },
    )

    handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has_not",
        value=f"",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "not_number"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 4

    view_filter.value = f"{select_options[0].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = f"{select_options[1].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    view_filter.value = f"{select_options[2].id}"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids

    # chaining filters should also work
    view_filter.value = f"{select_options[2].id}"
    view_filter.save()

    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has_not",
        value=f"{select_options[1].id}",
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_3.id in ids

    # Changing the view to use "OR" for multiple filters
    handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_3.id in ids


@pytest.mark.django_db
def test_multiple_select_has_and_empty_or_filter_no_duplicates(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    multiple_select_field = data_fixture.create_multiple_select_field(table=table)

    select_option_a = data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue"
    )
    select_option_b = data_fixture.create_select_option(
        field=multiple_select_field, value="B", color="red"
    )
    select_option_c = data_fixture.create_select_option(
        field=multiple_select_field, value="C", color="green"
    )

    handler = ViewHandler()
    model = table.get_model()

    row_empty = model.objects.create()

    row_single_a = model.objects.create()
    getattr(row_single_a, f"field_{multiple_select_field.id}").set([select_option_a.id])

    row_single_b = model.objects.create()
    getattr(row_single_b, f"field_{multiple_select_field.id}").set([select_option_b.id])

    row_multiple_ab = model.objects.create()
    getattr(row_multiple_ab, f"field_{multiple_select_field.id}").set(
        [select_option_a.id, select_option_b.id]
    )

    row_multiple_ac = model.objects.create()
    getattr(row_multiple_ac, f"field_{multiple_select_field.id}").set(
        [select_option_a.id, select_option_c.id]
    )

    handler.update_view(user=user, view=grid_view, filter_type="OR")

    data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="multiple_select_has",
        value=f"{select_option_a.id},{select_option_b.id}",
    )

    data_fixture.create_view_filter(
        view=grid_view,
        field=multiple_select_field,
        type="empty",
        value="",
    )

    queryset = handler.apply_filters(grid_view, model.objects.all())
    result_ids = [r.id for r in queryset.all()]

    expected_ids = {
        row_empty.id,
        row_single_a.id,
        row_single_b.id,
        row_multiple_ab.id,
        row_multiple_ac.id,
    }

    assert len(result_ids) == len(set(result_ids))

    assert set(result_ids) == expected_ids
    assert len(result_ids) == 5


@pytest.mark.django_db
def test_length_is_lower_than_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    long_text_field = data_fixture.create_long_text_field(table=table)
    url_field = data_fixture.create_url_field(table=table)
    email_field = data_fixture.create_email_field(table=table)
    phone_number_field = data_fixture.create_phone_number_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row_1 = model.objects.create(
        **{
            f"field_{text_field.id}": "t",
            f"field_{long_text_field.id}": "t",
            f"field_{url_field.id}": "t@test.com",
            f"field_{email_field.id}": "t@baserow.com",
            f"field_{phone_number_field.id}": "+44 1",
        }
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "te",
            f"field_{long_text_field.id}": "te",
            f"field_{url_field.id}": "te@test.com",
            f"field_{email_field.id}": "te@baserow.com",
            f"field_{phone_number_field.id}": "+44 12",
        }
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "tes",
            f"field_{long_text_field.id}": "tes",
            f"field_{url_field.id}": "tes@test.com",
            f"field_{email_field.id}": "te@baserow.com",
            f"field_{phone_number_field.id}": "+44 123",
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=text_field, type="length_is_lower_than", value=12
    )

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = 2
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = 3
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_2.id in ids

    view_filter.value = 4
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_2.id in ids
    assert row_3.id in ids

    # with an invalid filter value no results are returned
    view_filter.value = "a"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    view_filter.value = 2
    view_filter.field = long_text_field
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = 11
    view_filter.field = url_field
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = 6
    view_filter.field = phone_number_field
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids


@pytest.mark.django_db
def test_date_equals_day_of_month_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    last_modified_field_datetime_berlin = data_fixture.create_last_modified_field(
        table=table, date_include_time=True
    )

    handler = ViewHandler()
    model = table.get_model()

    with freeze_time("2020-1-03 22:01"):
        row_1 = model.objects.create(
            **{
                f"field_{date_field.id}": date(2021, 8, 11),
            }
        )
        row_2 = model.objects.create(
            **{
                f"field_{date_field.id}": date(2020, 1, 1),
            }
        )
        row_3 = model.objects.create(
            **{
                f"field_{date_field.id}": date(2019, 11, 1),
            }
        )
        model.objects.create(
            **{
                f"field_{date_field.id}": None,
            }
        )

    # Date Field (No timezone)
    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=date_field, type="date_equals_day_of_month", value="1"
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids

    view_filter.value = "11"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row_1.id in ids

    view_filter.value = "-1"
    view_filter.save()
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 0

    # Datetime (With timezone)

    # Jan 1st UTC, Jan 1st Germany, Jan 1st London
    with freeze_time("2020-1-01 22:01"):
        row_2_tz = model.objects.create(**{})

    # Jan 1st UTC, Jan 2nd Germany, Jan 1st London
    with freeze_time("2019-1-01 23:01"):
        row_3_tz = model.objects.create(**{})

    view_filter.field = last_modified_field_datetime_berlin
    view_filter.value = "1"
    view_filter.save()

    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert ids == unordered([row_2_tz.id, row_3_tz.id])


@pytest.mark.django_db
def test_link_row_contains_filter_type(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(
        primary=True, table=related_table
    )
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 1",
        },
    )
    related_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 2",
        },
    )
    related_row_3 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={
            f"field_{related_primary_field.id}": "Related row 3",
        },
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )
    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_row_1.id],
        },
    )
    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_row_2.id],
        },
    )
    row_3 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 3",
            f"field_{link_row_field.id}": [related_row_3.id],
        },
    )
    row_with_all_relations = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 4",
            f"field_{link_row_field.id}": [
                related_row_1.id,
                related_row_2.id,
                related_row_3.id,
            ],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 5

    view_filter.value = "nonsense"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 0

    view_filter.value = "row"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 4

    view_filter.value = "1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2
    assert row_1.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = "2"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_with_all_relations.id in ids

    view_filter.value = "3"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2
    assert row_3.id in ids
    assert row_with_all_relations.id in ids

    # Chaining filters should also work
    # creating a second filter for the same field
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value="1",
    )
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1
    assert row_with_all_relations.id in ids

    # Changing the view to use "OR" for multiple filters
    view_handler.update_view(user=user, view=grid_view, filter_type="OR")
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3
    assert row_1.id in ids
    assert row_3.id in ids
    assert row_with_all_relations.id in ids


@pytest.mark.django_db
def test_link_row_contains_filter_type_date_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_date_field = data_fixture.create_date_field(
        primary=True, table=related_table, date_format="ISO"
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_date_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_date_field.id}": "2020-02-01 01:23"},
    )

    related_date_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_date_field.id}": "2021-02-01 01:23"},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_date_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_date_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "2020"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "01"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_created_on_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    now = datetime.now(tz=timezone.utc)

    related_primary_created_on_field = data_fixture.create_created_on_field(
        primary=True, table=related_table
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_created_on_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
    )

    related_created_on_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_created_on_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_created_on_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = now.year
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_file_field(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_file_field = data_fixture.create_file_field(
        primary=True, table=related_table
    )

    file_one = data_fixture.create_user_file(original_name="target 1")
    file_two = data_fixture.create_user_file(original_name="target 2")

    model = table.get_model()
    related_model = related_table.get_model()

    related_file_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_file_field.id}": [{"name": file_one.name}]},
    )

    related_file_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_file_field.id}": [{"name": file_two.name}]},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_file_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_file_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "target 1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "target"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_single_select_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_single_select_field = data_fixture.create_single_select_field(
        primary=True, table=related_table
    )

    option_a = data_fixture.create_select_option(
        field=related_primary_single_select_field, value="target 1", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=related_primary_single_select_field, value="target 2", color="red"
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_single_select_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_single_select_field.id}": option_a.id},
    )

    related_single_select_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_single_select_field.id}": option_b.id},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_single_select_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_single_select_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "target 1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "target"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
def test_link_row_contains_filter_type_uuid_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_uuid_field = data_fixture.create_uuid_field(
        primary=True, table=related_table
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_uuid_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={},
    )

    related_uuid_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={},
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_uuid_row_1.id],
        },
    )

    row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_uuid_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    uuid_value = str(
        getattr(related_uuid_row_1, f"field_{related_primary_uuid_field.id}")
    )

    view_filter.value = uuid_value[:-2]
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1
    assert ids == [row_1.id]

    view_filter.value = uuid_value
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1
    assert ids == [row_1.id]


@pytest.mark.django_db
def test_link_row_contains_filter_type_multiple_select_field(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()

    related_primary_multiple_select_field = data_fixture.create_multiple_select_field(
        primary=True, table=related_table
    )

    option_a = data_fixture.create_select_option(
        field=related_primary_multiple_select_field, value="target 1", color="blue"
    )
    option_b = data_fixture.create_select_option(
        field=related_primary_multiple_select_field, value="target 2", color="red"
    )

    model = table.get_model()
    related_model = related_table.get_model()

    related_multiple_select_row_1 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_multiple_select_field.id}": [option_a.id]},
    )

    related_multiple_select_row_2 = row_handler.create_row(
        user=user,
        table=related_table,
        model=related_model,
        values={f"field_{related_primary_multiple_select_field.id}": [option_b.id]},
    )

    row_unrelated = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 0",
        },
    )

    row_1 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 1",
            f"field_{link_row_field.id}": [related_multiple_select_row_1.id],
        },
    )

    row_2 = row_handler.create_row(
        user=user,
        table=table,
        model=model,
        values={
            f"field_{primary_field.id}": "Row 2",
            f"field_{link_row_field.id}": [related_multiple_select_row_2.id],
        },
    )

    view_handler = ViewHandler()
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"",
    )

    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 3

    view_filter.value = "target 1"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 1

    view_filter.value = "target"
    view_filter.save()
    ids = [
        r.id for r in view_handler.apply_filters(grid_view, model.objects.all()).all()
    ]
    assert len(ids) == 2


@pytest.mark.django_db
@pytest.mark.disabled_in_ci
# You must add --run-disabled-in-ci -s to pytest to run this test, you can do this in
# intellij by editing the run config for this test and adding --run-disabled-in-ci -s
# to additional args.
def test_link_row_contains_filter_type_performance(data_fixture):
    rows_count = 5000
    related_rows_count = 5000
    relations_count = 50

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(database=database)
    related_table = data_fixture.create_database_table(database=database)
    primary_field = data_fixture.create_text_field(table=table)
    related_primary_field = data_fixture.create_text_field(
        primary=True, table=related_table
    )
    grid_view = data_fixture.create_grid_view(table=table)

    link_row_field = FieldHandler().create_field(
        user=user,
        table=table,
        type_name="link_row",
        name="Test",
        link_row_table=related_table,
    )

    row_handler = RowHandler()
    model = table.get_model()
    related_model = related_table.get_model()

    related_rows = []
    for i in range(related_rows_count):
        row = row_handler.create_row(
            user=user,
            table=related_table,
            model=related_model,
            values={
                f"field_{related_primary_field.id}": f"Related row {i}",
            },
        )
        related_rows.append(row)

    for i in range(rows_count):
        related_rows_chosen = random.sample(related_rows, relations_count)
        related_rows_chosen_ids = [row.id for row in related_rows_chosen]
        row_handler.create_row(
            user=user,
            table=table,
            model=model,
            values={
                f"field_{primary_field.id}": f"Row {i}",
                f"field_{link_row_field.id}": related_rows_chosen_ids,
            },
        )

    view_handler = ViewHandler()
    data_fixture.create_view_filter(
        view=grid_view,
        field=link_row_field,
        type="link_row_contains",
        value=f"related row",
    )

    profiler = Profiler()
    profiler.start()
    view_handler.apply_filters(grid_view, model.objects.all()).all()
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_empty_filter_type(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)

    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multi Collaborators"
    )
    ref_multiple_collaborators_field = data_fixture.create_formula_field(
        user=user, table=table, formula="field('Multi Collaborators')"
    )
    row_handler = RowHandler()
    model = table.get_model()
    row_1, row_2, empty_row = row_handler.force_create_rows(
        user=user,
        table=table,
        model=model,
        rows_values=[
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                    {"id": user2.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [],
            },
        ],
    ).created_rows
    handler = ViewHandler()
    for field in [multiple_collaborators_field, ref_multiple_collaborators_field]:
        grid_view = data_fixture.create_grid_view(table=table)
        view_filter = data_fixture.create_view_filter(
            view=grid_view,
            field=field,
            type="empty",
        )

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

        assert len(ids) == 1
        assert empty_row.id in ids


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_not_empty_filter_type(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)

    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multi Collaborators"
    )
    ref_multiple_collaborators_field = data_fixture.create_formula_field(
        user=user, table=table, formula="field('Multi Collaborators')"
    )
    row_handler = RowHandler()
    model = table.get_model()
    row_1, row_2, empty_row = row_handler.force_create_rows(
        user=user,
        table=table,
        model=model,
        rows_values=[
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                    {"id": user2.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [],
            },
        ],
    ).created_rows
    handler = ViewHandler()
    for field in [multiple_collaborators_field, ref_multiple_collaborators_field]:
        grid_view = data_fixture.create_grid_view(table=table)
        view_filter = data_fixture.create_view_filter(
            view=grid_view,
            field=field,
            type="not_empty",
        )

        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

        assert len(ids) == 2
        assert row_1.id in ids
        assert row_2.id in ids


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_has_filter_type(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multi Collaborators"
    )
    ref_multiple_collaborators_field = data_fixture.create_formula_field(
        user=user, table=table, formula="field('Multi Collaborators')"
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1, row_2, _, row_with_all_collaborators = row_handler.force_create_rows(
        user=user,
        table=table,
        model=model,
        rows_values=[
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                    {"id": user2.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [],
            },
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                    {"id": user2.id},
                    {"id": user3.id},
                ],
            },
        ],
    ).created_rows

    handler = ViewHandler()
    for field in [multiple_collaborators_field, ref_multiple_collaborators_field]:
        grid_view = data_fixture.create_grid_view(table=table)
        view_filter = data_fixture.create_view_filter(
            view=grid_view,
            field=field,
            type="multiple_collaborators_has",
            value=f"",
        )
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 4

        view_filter.value = "not_number"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 4

        view_filter.value = "-1"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 0

        view_filter.value = f"{user.id}"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        print(ids)
        assert len(ids) == 3
        assert row_1.id in ids
        assert row_2.id in ids
        assert row_with_all_collaborators.id in ids

        view_filter.value = f"{user2.id}"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_2.id in ids
        assert row_with_all_collaborators.id in ids

        # # chaining filters should also work
        view_filter.value = f"{user2.id}"
        view_filter.save()

        # creating a second filter for the same field
        data_fixture.create_view_filter(
            view=grid_view,
            field=multiple_collaborators_field,
            type="multiple_collaborators_has",
            value=f"{user.id}",
        )
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_2.id in ids
        assert row_with_all_collaborators.id in ids

        # # Changing the view to use "OR" for multiple filters
        handler.update_view(user=user, view=grid_view, filter_type="OR")
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 3
        assert row_1.id in ids
        assert row_2.id in ids
        assert row_with_all_collaborators.id in ids


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_has_not_filter_type(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    user3 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    grid_view = data_fixture.create_grid_view(table=table)

    multiple_collaborators_field = data_fixture.create_multiple_collaborators_field(
        user=user, table=table, name="Multi Collaborators"
    )
    ref_multiple_collaborators_field = data_fixture.create_formula_field(
        user=user, table=table, formula="field('Multi Collaborators')"
    )

    row_handler = RowHandler()
    model = table.get_model()

    row_1, row_2, row_3, _ = row_handler.force_create_rows(
        user=user,
        table=table,
        model=model,
        rows_values=[
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                    {"id": user2.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [
                    {"id": user2.id},
                    {"id": user3.id},
                ],
            },
            {
                multiple_collaborators_field.db_column: [],
            },
            {
                multiple_collaborators_field.db_column: [
                    {"id": user.id},
                    {"id": user2.id},
                    {"id": user3.id},
                ],
            },
        ],
    ).created_rows

    handler = ViewHandler()
    for field in [multiple_collaborators_field, ref_multiple_collaborators_field]:
        grid_view = data_fixture.create_grid_view(table=table)
        view_filter = data_fixture.create_view_filter(
            view=grid_view,
            field=field,
            type="multiple_collaborators_has_not",
            value=f"",
        )
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 4

        view_filter.value = "not_number"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 4

        view_filter.value = "-1"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 4

        view_filter.value = f"{user.id}"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_2.id in ids
        assert row_3.id in ids

        view_filter.value = f"{user2.id}"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row_3.id in ids

        view_filter.value = f"{user3.id}"
        view_filter.save()
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_1.id in ids
        assert row_3.id in ids

        # chaining filters should also work
        view_filter.value = f"{user3.id}"
        view_filter.save()

        # creating a second filter for the same field
        data_fixture.create_view_filter(
            view=grid_view,
            field=multiple_collaborators_field,
            type="multiple_collaborators_has_not",
            value=f"{user2.id}",
        )
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 1
        assert row_3.id in ids

        # Changing the view to use "OR" for multiple filters
        handler.update_view(user=user, view=grid_view, filter_type="OR")
        ids = [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]
        assert len(ids) == 2
        assert row_1.id in ids
        assert row_3.id in ids


@pytest.mark.django_db
@pytest.mark.field_multiple_collaborators
def test_multiple_collaborators_has_filter_type_export_import(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    view_filter_type = view_filter_type_registry.get("multiple_collaborators_has")
    assert (
        view_filter_type.get_export_serialized_value(
            f"{user.id}", {"workspace_id": workspace.id}
        )
        == f"{user.email}"
    )
    id_mapping = {"workspace_id": workspace.id}
    assert view_filter_type.set_import_serialized_value(user.email, id_mapping) == str(
        user.id
    )
    assert view_filter_type.set_import_serialized_value(user.email, {}) == ""
    assert view_filter_type.set_import_serialized_value("", id_mapping) == ""
    assert view_filter_type.set_import_serialized_value("wrong", id_mapping) == ""


@contextmanager
def rows_with_dates(data_fixture, dates, filter_type):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    rows = model.objects.bulk_create(
        [model(**{f"field_{date_field.id}": d}) for d in dates]
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=date_field,
        type=filter_type,
        value="",
    )

    def get_filtered_row_ids():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    yield rows, view_filter, get_filtered_row_ids


@contextmanager
def rows_with_datetimes(data_fixture, dates, filter_type):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table, date_include_time=True)

    handler = ViewHandler()
    model = table.get_model()

    rows = model.objects.bulk_create(
        [model(**{f"field_{date_field.id}": d}) for d in dates]
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=date_field,
        type=filter_type,
        value="",
    )

    def get_filtered_row_ids():
        return [
            r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()
        ]

    yield rows, view_filter, get_filtered_row_ids


@pytest.mark.django_db
def test_date_within_days_view_filter(data_fixture):
    dates = [
        date(2020, 12, 1),  # 0
        date(2021, 1, 1),  # 1
        date(2021, 1, 2),  # 2
        date(2021, 1, 3),  # 3
        date(2021, 1, 4),  # 4
        date(2021, 1, 5),  # 5
        date(2021, 1, 6),  # 6
        date(2021, 2, 1),  # 7
        date(2022, 1, 1),  # 8
    ]

    with rows_with_dates(data_fixture, dates, "date_within_days") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        with freeze_time("2021-01-02"):
            assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "1"
        view_filter.save()

        with freeze_time("2021-01-02"):
            assert get_filtered_row_ids() == [rows[2].id, rows[3].id]

        view_filter.value = "Europe/Rome?1"
        view_filter.save()

        with freeze_time("2021-01-04"):
            assert get_filtered_row_ids() == [rows[4].id, rows[5].id]

        with freeze_time(
            datetime(2021, 1, 4, 0, 0, 0, tzinfo=ZoneInfo("Pacific/Apia"))
        ):
            assert get_filtered_row_ids() == [rows[3].id, rows[4].id]


@pytest.mark.django_db
def test_date_within_weeks_view_filter(data_fixture):
    dates = [
        date(2020, 12, 1),  # 0
        date(2021, 1, 1),  # 1
        date(2021, 1, 7),  # 2
        date(2021, 1, 8),  # 3
        date(2021, 1, 14),  # 4
        date(2021, 1, 15),  # 5
        date(2021, 1, 18),  # 6
        date(2021, 2, 1),  # 7
        date(2022, 1, 1),  # 8
    ]

    with rows_with_dates(data_fixture, dates, "date_within_weeks") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        with freeze_time("2021-01-02"):
            assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "1"
        view_filter.save()

        with freeze_time("2021-01-01"):
            assert get_filtered_row_ids() == [rows[1].id, rows[2].id, rows[3].id]

        view_filter.value = "Europe/Rome?2"
        view_filter.save()

        with freeze_time("2021-01-08"):
            assert get_filtered_row_ids() == [
                rows[3].id,
                rows[4].id,
                rows[5].id,
                rows[6].id,
            ]

        with freeze_time(
            datetime(2021, 1, 8, 0, 0, 0, tzinfo=ZoneInfo("Pacific/Apia"))
        ):
            assert get_filtered_row_ids() == [
                rows[2].id,
                rows[3].id,
                rows[4].id,
                rows[5].id,
                rows[6].id,
            ]


@pytest.mark.django_db
def test_date_within_months_view_filter(data_fixture):
    dates = [
        date(2020, 12, 1),  # 0
        date(2021, 1, 1),  # 1
        date(2021, 1, 7),  # 2
        date(2021, 1, 31),  # 3
        date(2021, 2, 1),  # 4
        date(2021, 2, 15),  # 5
        date(2021, 3, 1),  # 6
        date(2021, 3, 21),  # 7
        date(2022, 1, 1),  # 8
    ]

    with rows_with_dates(data_fixture, dates, "date_within_months") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        with freeze_time("2021-01-02"):
            assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "1"
        view_filter.save()

        with freeze_time("2021-01-02"):
            assert get_filtered_row_ids() == [rows[2].id, rows[3].id, rows[4].id]

        view_filter.value = "Europe/Rome?2"
        view_filter.save()

        with freeze_time("2021-01-08"):
            assert get_filtered_row_ids() == [
                rows[3].id,
                rows[4].id,
                rows[5].id,
                rows[6].id,
            ]

        with freeze_time(
            datetime(2021, 1, 8, 0, 0, 0, tzinfo=ZoneInfo("Pacific/Apia"))
        ):
            assert get_filtered_row_ids() == [
                rows[2].id,
                rows[3].id,
                rows[4].id,
                rows[5].id,
                rows[6].id,
            ]


@pytest.mark.django_db
def test_before_or_equal_datetime_view_filter(data_fixture):
    dates = [
        datetime(2020, 12, 1, 12, 30, 0, 0, tzinfo=timezone.utc),  # 0
        datetime(2021, 1, 1, 18, 30, 0, 0, tzinfo=timezone.utc),  # 1
        datetime(2021, 1, 2, 3, 30, 0, 0, tzinfo=timezone.utc),  # 2
    ]

    with rows_with_datetimes(data_fixture, dates, "date_before_or_equal") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "2022-01-02"
        view_filter.save()

        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "Europe/Rome?2021-01-02"
        view_filter.save()

        assert get_filtered_row_ids() == [rows[0].id, rows[1].id, rows[2].id]

        view_filter.value = "Australia/Melbourne?2021-01-01"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[0].id]

        view_filter.value = "Pacific/Honolulu?2021-01-01"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[0].id, rows[1].id, rows[2].id]


@pytest.mark.django_db
def test_before_or_equal_date_view_filter(data_fixture):
    dates = [
        date(2020, 12, 1),  # 0
        date(2021, 1, 1),  # 1
        date(2021, 1, 2),  # 2
    ]

    with rows_with_dates(data_fixture, dates, "date_before_or_equal") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "2022-01-02"
        view_filter.save()

        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "Europe/Rome?2021-01-02"
        view_filter.save()

        assert get_filtered_row_ids() == [rows[0].id, rows[1].id, rows[2].id]

        view_filter.value = "Australia/Melbourne?2021-01-01"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[0].id, rows[1].id]

        view_filter.value = "Pacific/Honolulu?2021-01-01"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[0].id, rows[1].id]


@pytest.mark.django_db
def test_after_or_equal_datetime_view_filter(data_fixture):
    dates = [
        datetime(2020, 12, 1, 12, 30, 0, 0, tzinfo=timezone.utc),  # 0
        datetime(2021, 1, 1, 14, 30, 0, 0, tzinfo=timezone.utc),  # 1
        datetime(2021, 1, 2, 3, 30, 0, 0, tzinfo=timezone.utc),  # 2
    ]

    with rows_with_datetimes(data_fixture, dates, "date_after_or_equal") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "2020-12-01"
        view_filter.save()

        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "Europe/Rome?2020-12-01"
        view_filter.save()

        assert get_filtered_row_ids() == [rows[0].id, rows[1].id, rows[2].id]

        view_filter.value = "Australia/Melbourne?2021-01-02"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[1].id, rows[2].id]

        view_filter.value = "Pacific/Honolulu?2021-01-02"
        view_filter.save()
        assert get_filtered_row_ids() == []


@pytest.mark.django_db
def test_after_or_equal_date_view_filter(data_fixture):
    dates = [
        date(2020, 12, 1),  # 0
        date(2021, 1, 1),  # 1
        date(2021, 1, 2),  # 2
    ]

    with rows_with_dates(data_fixture, dates, "date_after_or_equal") as (
        rows,
        view_filter,
        get_filtered_row_ids,
    ):
        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "2020-12-01"
        view_filter.save()

        assert len(get_filtered_row_ids()) == len(dates)

        view_filter.value = "Europe/Rome?2020-12-01"
        view_filter.save()

        assert get_filtered_row_ids() == [rows[0].id, rows[1].id, rows[2].id]

        view_filter.value = "Australia/Melbourne?2021-01-01"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[1].id, rows[2].id]

        view_filter.value = "Pacific/Honolulu?2021-01-01"
        view_filter.save()
        assert get_filtered_row_ids() == [rows[1].id, rows[2].id]


@pytest.mark.django_db
def test_date_after_days_ago_filter_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table, date_include_time=False)

    model = table.get_model()

    row_day_1 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2023, 1, 1),
        }
    )
    row_day_2 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2023, 1, 2),
        }
    )
    row_day_3 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2023, 1, 3),
        }
    )
    row_day_4 = model.objects.create(
        **{
            f"field_{date_field.id}": date(2023, 1, 4),
        }
    )
    handler = ViewHandler()

    filter = data_fixture.create_view_filter(
        view=grid_view,
        field=date_field,
        type="date_after_days_ago",
        value="UTC?1",
    )

    def apply_filter():
        return list(handler.apply_filters(grid_view, model.objects.all()).all())

    with freeze_time("2023-01-04 10:00", tz_offset=2):
        filter.value = "Europe/Berlin?2"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_2, row_day_3, row_day_4]

    with freeze_time("2023-01-04 10:00"):
        filter.value = "UTC?3"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_1, row_day_2, row_day_3, row_day_4]

    with freeze_time("2023-01-04 10:00"):
        filter.value = "1"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_3, row_day_4]

    with freeze_time("2023-01-04 10:00"):
        filter.value = "0"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_1, row_day_2, row_day_3, row_day_4]

    with freeze_time("2023-01-04 10:00"):
        filter.value = " "
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_1, row_day_2, row_day_3, row_day_4]

    with freeze_time("2023-01-04 10:00", tz_offset=0):
        filter.value = "GMT?1"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_3, row_day_4]

    with freeze_time("2023-01-04 11:00", tz_offset=1):
        filter.value = "CET?1"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_3, row_day_4]

    with freeze_time("2019-01-04 11:00"):
        filter.value = "UTC?100"
        filter.save()
        rows = apply_filter()
        assert rows == [row_day_1, row_day_2, row_day_3, row_day_4]

    with freeze_time("2019-01-04 11:00"):
        filter.value = "ABC"
        filter.save()
        rows = apply_filter()
        assert rows == []


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_user_is_filter_type(data_fixture):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_by_field = data_fixture.create_last_modified_by_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"last_modified_by": user,
        }
    )
    row_2 = model.objects.create(
        **{
            f"last_modified_by": user2,
        }
    )
    row_3 = model.objects.create(
        **{
            f"last_modified_by": None,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_by_field,
        type="user_is",
        value=user.id,
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 1
    assert row.id in ids


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_user_is_not_filter_type(data_fixture):
    user = data_fixture.create_user()
    user2 = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    last_modified_by_field = data_fixture.create_last_modified_by_field(table=table)

    handler = ViewHandler()
    model = table.get_model()

    row = model.objects.create(
        **{
            f"last_modified_by": user,
        }
    )
    row_2 = model.objects.create(
        **{
            f"last_modified_by": user2,
        }
    )
    row_3 = model.objects.create(
        **{
            f"last_modified_by": None,
        }
    )

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=last_modified_by_field,
        type="user_is_not",
        value=user.id,
    )
    ids = [r.id for r in handler.apply_filters(grid_view, model.objects.all()).all()]
    assert len(ids) == 2
    assert row_2.id in ids
    assert row_3.id in ids


@pytest.mark.field_last_modified_by
@pytest.mark.django_db
def test_user_is_filter_type_export_import(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    view_filter_type = view_filter_type_registry.get("user_is")
    assert (
        view_filter_type.get_export_serialized_value(
            f"{user.id}", {"workspace_id": workspace.id}
        )
        == f"{user.email}"
    )
    id_mapping = {"workspace_id": workspace.id}
    assert view_filter_type.set_import_serialized_value(user.email, id_mapping) == str(
        user.id
    )
    assert view_filter_type.set_import_serialized_value(user.email, {}) == ""
    assert view_filter_type.set_import_serialized_value("", id_mapping) == ""
    assert view_filter_type.set_import_serialized_value("wrong", id_mapping) == ""


@pytest.mark.django_db
def test_duplicate_table_single_select_is_one_of(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(field=field, value="AAA", color="blue")
    option_2 = data_fixture.create_select_option(field=field, value="BBB", color="red")

    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=field,
        type="single_select_is_any_of",
        value=f"{option_1.id},{option_2.id}",
    )

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicated_view = duplicated_table.view_set.first()
    duplicated_field = duplicated_table.field_set.first().specific
    duplicated_options = duplicated_field.select_options.all()
    duplicated_filter = ViewFilter.objects.filter(view=duplicated_view).first()

    assert (
        duplicated_filter.value
        == f"{duplicated_options[0].id},{duplicated_options[1].id}"
    )
    assert duplicated_filter.value != f"{option_1.id},{option_2.id}"


@pytest.mark.django_db
def test_ensure_all_multi_step_filter_type_and_operators_are_tested(data_fixture):
    for filter_type in view_filter_type_registry.get_all():
        if not isinstance(filter_type, DateMultiStepViewFilterType):
            continue
        assert filter_type.type in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS
        for operator in filter_type.get_available_operators():
            assert (
                operator in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS[filter_type.type]
            ), f"{filter_type.type} is missing test for {operator.value}"
            assert (
                "expected_results"
                in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS[filter_type.type][operator]
            ), f"'expected_results' missing for {filter_type.type} - {operator.value}"


@pytest.fixture()
def table_view_fields_rows(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    date_field = data_fixture.create_date_field(table=table)
    datetime_field = data_fixture.create_date_field(table=table, date_include_time=True)
    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            [
                {
                    date_field.db_column: date_value,
                    datetime_field.db_column: date_value,
                }
                for date_value in TEST_MULTI_STEP_DATE_OPERATORS_DATETIMES
            ],
        )
        .created_rows
    )
    return table, grid_view, date_field, datetime_field, rows


@pytest.mark.parametrize(
    "filter_type,operator,filter_value,expected_results",
    [
        (
            filter_type,
            opr.value,
            opr_data.get("value", ""),
            [MNEMONIC_VALUES[v] for v in opr_data["expected_results"]],
        )
        for filter_type in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS.keys()
        for (opr, opr_data) in DATE_MULTI_STEP_OPERATOR_VALID_RESULTS[
            filter_type
        ].items()
    ],
)
@pytest.mark.django_db
def test_date_equal_multi_step_operator_view_filter_type(
    data_fixture,
    filter_type,
    operator,
    filter_value,
    expected_results,
    table_view_fields_rows,
):
    table, grid_view, date_field, datetime_field, rows = table_view_fields_rows

    handler = ViewHandler()
    model = table.get_model()

    def apply_filters_and_assert():
        with freeze_time(FREEZED_TODAY):
            qs = handler.apply_filters(grid_view, model.objects.all())
            ids = set([r.id for r in qs.all()])
        res_pos = [i for (i, r) in enumerate(rows) if r.id in ids]

        mnem_keys = list(MNEMONIC_VALUES.keys())
        mnem_res_pos = [mnem_keys[v] for v in res_pos]
        mnem_exp_res = [mnem_keys[v] for v in expected_results]
        assert res_pos == unordered(
            expected_results
        ), f"{filter_type} - {operator}: {mnem_res_pos} != {mnem_exp_res}"

    # with date
    view_filter = data_fixture.create_view_filter(
        view=grid_view,
        field=date_field,
        type=filter_type,
        value=f"UTC?{filter_value}?{operator}",
    )

    apply_filters_and_assert()

    # with datetime
    view_filter.field = datetime_field
    view_filter.save()

    apply_filters_and_assert()


@pytest.mark.django_db
def test_duplicate_table_with_two_nested_filter_groups(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_text_field(table=table)

    group_1 = data_fixture.create_view_filter_group(user=user, view=view)
    group_2 = data_fixture.create_view_filter_group(
        user=user, view=view, parent_group=group_1
    )
    data_fixture.create_view_filter(user=user, view=view, group=group_2)

    duplicated_table = TableHandler().duplicate_table(user, table)
    duplicates_view = duplicated_table.view_set.first()
    filter_groups = duplicates_view.filter_groups.all()
    assert len(filter_groups) == 2
    assert filter_groups[0].parent_group is None
    assert filter_groups[1].parent_group_id == filter_groups[0].id


@pytest.mark.django_db
def test_all_view_filters_can_accept_strings_as_filter_value(data_fixture):
    table, user, row, _, context = setup_interesting_test_table(data_fixture)
    view = data_fixture.create_grid_view(table=table)
    fields = context["fields"]
    for field in fields.values():
        for view_filter_type in view_filter_type_registry.get_all():
            if not view_filter_type.field_is_compatible(field):
                continue

            data_fixture.create_view_filter(
                view=view,
                field=field,
                type=view_filter_type.type,
                value="test",
            )

    # We should be able to load the view without any errors
    handler = ViewHandler()
    try:
        handler.get_queryset(user, view)
    except Exception as e:
        pytest.fail(f"Exception raised: {e}")


@pytest.mark.django_db
def test_week_operator_for_view_multi_date_filters(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    date_field = data_fixture.create_date_field(table=table)
    view = data_fixture.create_grid_view(table=table)
    rows = (
        RowHandler()
        .force_create_rows(
            user=user,
            table=table,
            rows_values=[
                {date_field.db_column: date(2025, 3, 16)},
                {date_field.db_column: date(2025, 3, 17)},  # MO-1
                {date_field.db_column: date(2025, 3, 23)},
                {date_field.db_column: date(2025, 3, 24)},  # MO
                {date_field.db_column: date(2025, 3, 25)},
                {date_field.db_column: date(2025, 3, 26)},
                {date_field.db_column: date(2025, 3, 27)},
                {date_field.db_column: date(2025, 3, 28)},
                {date_field.db_column: date(2025, 3, 29)},
                {date_field.db_column: date(2025, 3, 30)},
                {date_field.db_column: date(2025, 3, 31)},  # MO+1
                {date_field.db_column: date(2025, 4, 1)},
                {date_field.db_column: date(2025, 4, 6)},
                {date_field.db_column: date(2025, 4, 7)},  # MO+2
            ],
        )
        .created_rows
    )

    view_filter = data_fixture.create_view_filter(
        view=view,
        field=date_field,
        type="date_is",
        value="Europe/Rome??this_week",
    )

    handler = ViewHandler()
    model = table.get_model()
    for day in range(24, 30):  # MO-SU
        with freeze_time(f"2025-03-{day}"):
            qs = handler.apply_filters(view, model.objects.all())
            [getattr(r, date_field.db_column) for r in qs.all()] == [
                date(2025, 3, 24),
                date(2025, 3, 25),
                date(2025, 3, 26),
                date(2025, 3, 27),
                date(2025, 3, 28),
                date(2025, 3, 29),
                date(2025, 3, 30),
            ]

    view_filter.value = "Europe/Rome??one_week_ago"
    view_filter.save()

    for day in range(24, 30):  # MO-SU
        with freeze_time(f"2025-03-{day}"):
            qs = handler.apply_filters(view, model.objects.all())
            [getattr(r, date_field.db_column) for r in qs.all()] == [
                date(2025, 3, 17),
                date(2025, 3, 18),
                date(2025, 3, 23),
            ]

    view_filter.value = "Europe/Rome?2?nr_weeks_ago"
    view_filter.save()

    for day in range(24, 30):  # MO-SU
        with freeze_time(f"2025-03-{day}"):
            qs = handler.apply_filters(view, model.objects.all())
            [getattr(r, date_field.db_column) for r in qs.all()] == [
                date(2025, 3, 16),
            ]

    view_filter.value = "Europe/Rome??next_week"
    view_filter.save()

    for day in range(24, 30):  # MO-SU
        with freeze_time(f"2025-03-{day}"):
            qs = handler.apply_filters(view, model.objects.all())
            [getattr(r, date_field.db_column) for r in qs.all()] == [
                date(2025, 3, 31),
                date(2025, 4, 1),
                date(2025, 4, 6),
            ]

    view_filter.value = "Europe/Rome??next_week"
    view_filter.save()

    for day in range(24, 30):  # MO-SU
        with freeze_time(f"2025-03-{day}"):
            qs = handler.apply_filters(view, model.objects.all())
            [getattr(r, date_field.db_column) for r in qs.all()] == [
                date(2025, 3, 31),
                date(2025, 4, 1),
                date(2025, 4, 6),
            ]

    view_filter.value = "Europe/Rome?2?nr_weeks_from_now"
    view_filter.save()

    for day in range(24, 30):  # MO-SU
        with freeze_time(f"2025-03-{day}"):
            qs = handler.apply_filters(view, model.objects.all())
            [getattr(r, date_field.db_column) for r in qs.all()] == [
                date(2025, 4, 7),
            ]


@pytest.mark.parametrize(
    "field_factory",
    [
        text_field_factory,
        long_text_field_factory,
        email_field_factory,
        phone_number_field_factory,
        number_field_factory,
        url_field_factory,
        single_select_field_factory,
        multiple_select_field_factory,
        date_field_factory,
        datetime_field_factory,
        duration_field_factory,
        multiple_collaborators_field_factory,
        file_field_factory,
    ],
)
@pytest.mark.django_db
def test_empty_not_empty_formula_filter(field_factory, data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    target_field = field_factory(data_fixture, table, user)
    ref_target_field = data_fixture.create_formula_field(
        name="ref_field",
        table=table,
        formula=f"field('target')",
    )
    assert ref_target_field.error is None
    ref_ref_target_field = data_fixture.create_formula_field(
        name="ref_ref_field",
        table=table,
        formula=f"field('ref_field')",
    )
    assert ref_ref_target_field.error is None

    view = data_fixture.create_grid_view(user=user, table=table)
    row_handler = RowHandler()

    field_type = target_field.get_type()
    row_empty_1, row_empty_2 = row_handler.force_create_rows(
        user, table, [{}, {}]
    ).created_rows

    random_value = field_type.random_value(target_field, data_fixture.fake, {})
    r3_value = field_type.random_to_input_value(target_field, random_value)
    assert r3_value  # Ensure we're not getting empty value
    row_3 = row_handler.force_create_row(
        user, table, {target_field.db_column: r3_value}
    )

    for field in [target_field, ref_target_field, ref_ref_target_field]:
        view_filter = data_fixture.create_view_filter(
            view=view, field=field, type="empty"
        )

        model = table.get_model()

        handler = ViewHandler()
        ids = [r.id for r in handler.apply_filters(view, model.objects.all()).all()]
        assert ids == [row_empty_1.id, row_empty_2.id]

        view_filter.type = "not_empty"
        view_filter.save()

        ids = [r.id for r in handler.apply_filters(view, model.objects.all()).all()]
        assert ids == [row_3.id]

        view_filter.delete()
