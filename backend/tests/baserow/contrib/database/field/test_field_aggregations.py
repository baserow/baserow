from datetime import datetime, timezone
from decimal import Decimal

import pytest

from baserow.contrib.database.fields.field_aggregations import (
    AverageFieldAggregationType,
    CheckedFieldAggregationType,
    CheckedPercentageFieldAggregationType,
    CountFieldAggregationType,
    EarliestDateFieldAggregationType,
    EmptyCountFieldAggregationType,
    EmptyPercentageFieldAggregationType,
    LatestDateFieldAggregationType,
    MaxFieldAggregationType,
    MedianFieldAggregationType,
    MinFieldAggregationType,
    NotCheckedFieldAggregationType,
    NotCheckedPercentageFieldAggregationType,
    NotEmptyCountFieldAggregationType,
    NotEmptyPercentageFieldAggregationType,
    StdDevFieldAggregationType,
    SumFieldAggregationType,
    UniqueCountFieldAggregationType,
    VarianceFieldAggregationType,
)
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
def test_field_agg_compute_final_aggregation():
    """
    Check for division by zero.
    """

    agg_type = EmptyPercentageFieldAggregationType()

    result = agg_type._compute_final_aggregation(0, 0)
    assert result == 0

    result = agg_type._compute_final_aggregation(10, 0)
    assert result == 0


@pytest.mark.django_db
def test_field_agg_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 4},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    agg_type = CountFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 3


@pytest.mark.django_db
def test_field_agg_empty_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 4},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    agg_type = EmptyCountFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 2


@pytest.mark.django_db
def test_field_agg_not_empty_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    agg_type = NotEmptyCountFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 3


@pytest.mark.django_db
def test_field_agg_checked_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_boolean_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": True},
            {f"field_{field.id}": True},
            {f"field_{field.id}": True},
            {f"field_{field.id}": False},
            {f"field_{field.id}": False},
        ],
    )
    agg_type = CheckedFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 3


@pytest.mark.django_db
def test_field_agg_not_checked_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_boolean_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": True},
            {f"field_{field.id}": True},
            {f"field_{field.id}": True},
            {f"field_{field.id}": False},
            {f"field_{field.id}": False},
        ],
    )
    agg_type = NotCheckedFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 2


@pytest.mark.django_db
def test_field_agg_empty_percentage(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 4},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    agg_type = EmptyPercentageFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert round(result, 2) == round(66.6666, 2)


@pytest.mark.django_db
def test_field_agg_not_empty_percentage(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 4},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    agg_type = NotEmptyPercentageFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert round(result, 2) == round(33.3333, 2)


@pytest.mark.django_db
def test_field_agg_checked_percentage(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_boolean_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": True},
            {f"field_{field.id}": False},
            {f"field_{field.id}": False},
            {f"field_{field.id}": False},
        ],
    )
    agg_type = CheckedPercentageFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 25.0


@pytest.mark.django_db
def test_field_agg_not_checked_percentage(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_boolean_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": True},
            {f"field_{field.id}": True},
            {f"field_{field.id}": True},
            {f"field_{field.id}": False},
        ],
    )
    agg_type = NotCheckedPercentageFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 25.0


@pytest.mark.django_db
def test_field_agg_unique_count(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = UniqueCountFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 3


@pytest.mark.django_db
def test_field_agg_min(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
            {f"field_{field.id}": 10},
        ],
    )
    agg_type = MinFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 2


@pytest.mark.django_db
def test_field_agg_max(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = MaxFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 10


@pytest.mark.django_db
def test_field_agg_earliest(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_date_field(table=table, date_include_time=True)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2025, 1, 1, 18, 20, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2025, 1, 1, 18, 10, tzinfo=timezone.utc)},
        ],
    )
    agg_type = EarliestDateFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_field_agg_latest(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_date_field(table=table, date_include_time=True)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2024, 1, 2, 12, 0, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2025, 1, 1, 18, 20, tzinfo=timezone.utc)},
            {f"field_{field.id}": datetime(2025, 1, 1, 18, 10, tzinfo=timezone.utc)},
        ],
    )
    agg_type = LatestDateFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == datetime(2025, 1, 1, 18, 20, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_field_agg_sum(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = SumFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 23


@pytest.mark.django_db
def test_field_agg_average(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = AverageFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == Decimal("4.6")


@pytest.mark.django_db
def test_field_agg_stddev(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = StdDevFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == Decimal("2.9393876913398137")


@pytest.mark.django_db
def test_field_agg_variance(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = VarianceFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == Decimal("8.64")


@pytest.mark.django_db
def test_field_agg_median(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    model = table.get_model()
    model_field = model._meta.get_field(field.db_column)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 5},
        ],
    )
    agg_type = MedianFieldAggregationType()

    result = agg_type.aggregate(model.objects, model_field, field)

    assert result == 4.0
