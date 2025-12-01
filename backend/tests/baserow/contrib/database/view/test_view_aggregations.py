import random
from decimal import Decimal

import pytest
from faker import Faker

from baserow.contrib.database.fields.exceptions import FieldNotInTable
from baserow.contrib.database.fields.field_types import SingleSelectFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.exceptions import FieldAggregationNotSupported
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_aggregation_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import setup_interesting_test_table


@pytest.mark.django_db
def test_view_empty_count_aggregation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    number_field = data_fixture.create_number_field(table=table)
    boolean_field = data_fixture.create_boolean_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    view_handler = ViewHandler()

    model = table.get_model()
    model.objects.create(
        **{
            f"field_{text_field.id}": "Aaa",
            f"field_{number_field.id}": 30,
            f"field_{boolean_field.id}": True,
        }
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "Aaa",
            f"field_{number_field.id}": 20,
            f"field_{boolean_field.id}": False,
        }
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "",
            f"field_{number_field.id}": 0,
            f"field_{boolean_field.id}": True,
        }
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": None,
            f"field_{number_field.id}": None,
            f"field_{boolean_field.id}": False,
        }
    )

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                text_field,
                "empty_count",
            ),
            (
                boolean_field,
                "empty_count",
            ),
            (
                number_field,
                "empty_count",
            ),
        ],
    )

    assert result[f"field_{text_field.id}"] == 2
    assert result[f"field_{boolean_field.id}"] == 2
    assert result[f"field_{number_field.id}"] == 1

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                text_field,
                "not_empty_count",
            ),
            (
                boolean_field,
                "not_empty_count",
            ),
            (
                number_field,
                "not_empty_count",
            ),
        ],
    )
    assert result[f"field_{text_field.id}"] == 2
    assert result[f"field_{boolean_field.id}"] == 2
    assert result[f"field_{number_field.id}"] == 3

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                text_field,
                "empty_count",
            ),
        ],
        with_total=True,
    )

    assert result[f"total"] == 4


@pytest.mark.django_db
def test_view_empty_count_aggregation_for_interesting_table(data_fixture):
    user = data_fixture.create_user()
    table, _, _, _, context = setup_interesting_test_table(data_fixture, user=user)
    grid_view = data_fixture.create_grid_view(table=table)

    model = table.get_model()

    view_handler = ViewHandler()

    aggregation_query = []
    aggregation_type = view_aggregation_type_registry.get("empty_count")

    compatible_fields = []
    for field in model._field_objects.values():
        if aggregation_type.field_is_compatible(field["field"]):
            compatible_fields.append(field["field"])

    for field in compatible_fields:
        aggregation_query.append((field, aggregation_type.type))

    result_empty = view_handler.get_field_aggregations(
        user, grid_view, aggregation_query, model=model, with_total=True
    )

    aggregation_query = []
    aggregation_type = view_aggregation_type_registry.get("not_empty_count")
    for field in compatible_fields:
        aggregation_query.append((field, aggregation_type.type))

    result_not_empty = view_handler.get_field_aggregations(
        user, grid_view, aggregation_query, model=model
    )

    for field in compatible_fields:
        assert (
            result_empty[field.db_column] + result_not_empty[field.db_column]
            == result_empty["total"]
        )


@pytest.mark.django_db
def test_view_unique_count_aggregation_for_interesting_table(data_fixture):
    user = data_fixture.create_user()
    table, _, _, _, context = setup_interesting_test_table(data_fixture, user=user)
    grid_view = data_fixture.create_grid_view(table=table)

    model = table.get_model()

    view_handler = ViewHandler()

    aggregation_type = view_aggregation_type_registry.get("unique_count")

    aggregation_query = []
    for field in model._field_objects.values():
        if aggregation_type.field_is_compatible(field["field"]):
            aggregation_query.append(
                (
                    field["field"],
                    "unique_count",
                )
            )

    result = view_handler.get_field_aggregations(
        user, grid_view, aggregation_query, model=model, with_total=True
    )

    assert (
        len(result.keys()) == len(aggregation_query) + 1
    ), f"{result} vs {aggregation_query}"

    for field_obj in model._field_objects.values():
        field = field_obj["field"]
        if aggregation_type.field_is_compatible(field):
            field_id = field.id
            field_type = field_obj["type"].type

            if (
                field_type
                in [
                    "url",
                    "email",
                    "rating",
                    "phone_number",
                    "count",
                    "rollup",
                ]
                or field_type == "formula"
                and field.formula_type == "char"
            ):
                assert result[f"field_{field_id}"] == 2
            else:
                assert result[f"field_{field_id}"] == 1


@pytest.mark.django_db
def test_view_number_aggregation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    number_field = data_fixture.create_number_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table)

    view_handler = ViewHandler()

    model = table.get_model()

    random.seed(12345)

    for i in range(30):
        model.objects.create(
            **{
                number_field.db_column: random.randint(0, 100),
            }
        )

    model.objects.create(
        **{
            number_field.db_column: None,
        }
    )

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "min",
            ),
        ],
    )
    assert result[number_field.db_column] == 1

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "max",
            ),
        ],
    )
    assert result[number_field.db_column] == 94

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "sum",
            ),
        ],
    )

    assert result[number_field.db_column] == 1546

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "average",
            ),
        ],
    )
    assert round(result[number_field.db_column], 2) == Decimal("51.53")

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "median",
            ),
        ],
    )
    assert round(result[number_field.db_column], 2) == Decimal("52.5")

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "std_dev",
            ),
        ],
    )
    assert round(result[number_field.db_column], 2) == Decimal("26.73")

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "variance",
            ),
        ],
    )
    assert round(result[number_field.db_column], 2) == Decimal("714.72")

    result = view_handler.get_field_aggregations(
        user,
        grid_view,
        [
            (
                number_field,
                "decile",
            ),
        ],
    )
    assert list(map(lambda x: round(x, 1), result[number_field.db_column])) == [
        19.5,
        22.8,
        33.7,
        46.2,
        52.5,
        58.6,
        70.3,
        74.8,
        93.0,
    ]


@pytest.mark.django_db
def test_view_aggregation_errors(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    form_view = data_fixture.create_form_view(table=table)

    table2 = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table2)
    grid_view = data_fixture.create_grid_view(table=table2)

    view_handler = ViewHandler()

    with pytest.raises(FieldAggregationNotSupported):
        view_handler.get_field_aggregations(
            user,
            form_view,
            [
                (
                    text_field,
                    "empty_count",
                ),
            ],
        )

    with pytest.raises(FieldNotInTable):
        view_handler.get_field_aggregations(
            user,
            grid_view,
            [
                (
                    text_field,
                    "empty_count",
                ),
            ],
        )


@pytest.mark.django_db
def test_aggregation_is_updated_when_view_is_trashed(data_fixture):
    """
    Test that aggregation is updated when view is trashed

    The following scenario is tested:
    - Create two views
    - Creat a field in both views
    - Create and aggregation in both views
    - Trash that view
    - Change the field type to a different type that is
      incompatible with the aggregation
    - Restore the view
    - Check that the aggregation is updated
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    grid_view_one = data_fixture.create_grid_view(table=table)
    grid_view_two = data_fixture.create_grid_view(table=table)
    field = data_fixture.create_number_field(user=user, table=table)
    application = table.database

    view_handler = ViewHandler()

    model = table.get_model()

    model.objects.create(**{field.db_column: 1})
    model.objects.create(**{field.db_column: 2})

    view_handler.update_field_options(
        view=grid_view_one,
        field_options={
            field.id: {
                "aggregation_type": "sum",
                "aggregation_raw_type": "sum",
            }
        },
    )

    view_handler.update_field_options(
        view=grid_view_two,
        field_options={
            field.id: {
                "aggregation_type": "sum",
                "aggregation_raw_type": "sum",
            }
        },
    )

    # Verify both views have an aggregation
    aggregations_view_one = view_handler.get_view_field_aggregations(
        user, grid_view_one
    )
    aggregations_view_two = view_handler.get_view_field_aggregations(
        user, grid_view_two
    )

    assert field.db_column in aggregations_view_one
    assert field.db_column in aggregations_view_two

    # Trash the view and verify that the aggregation is not retrievable anymore
    TrashHandler().trash(
        user, application.workspace, application, trash_item=grid_view_one
    )
    aggregations = view_handler.get_view_field_aggregations(user, grid_view_one)

    assert field.db_column not in aggregations

    # Update the field and verify that the aggregation is removed from the
    # not trashed view
    FieldHandler().update_field(user, field, new_type_name="text")
    aggregations_not_trashed_view = view_handler.get_view_field_aggregations(
        user, grid_view_two
    )
    assert field.db_column not in aggregations_not_trashed_view

    # Restore the view and verify that the aggregation
    # is also removed from the restored view
    TrashHandler().restore_item(user, "view", grid_view_one.id)
    aggregations_restored_view = view_handler.get_view_field_aggregations(
        user, grid_view_one
    )
    assert field.db_column not in aggregations_restored_view


@pytest.mark.django_db
class TestViewDistributionAggregation:
    def setup_method(self):
        self.test_fields = []
        self.random_values = {}
        self.expected_distributions = {}
        self.fake = Faker()
        self.cache = {}

    def create_random_values_and_expected_distributions(self, field):
        """
        Given a field, generates ten random values of its corresponding type.
        The first value is generated randomly. The next nine have a 50% chance
        of either being generated randomly or being repeated from the existing
        values. This produces a list of ten randomly generated values with some
        repetition, which is ideal for testing the distribution aggregation.
        Then we determine the expected distribution of those randomly generated
        values in order to assert the aggregation workes correctly later.
        """

        field_type = field.get_type()
        first_value = field_type.random_value(field, self.fake, self.cache)
        random_values = [first_value]
        for _ in range(9):
            if random.choice([True, False]):
                next_value = field_type.random_value(field, self.fake, self.cache)
            else:
                next_value = random.choice(random_values)
            random_values.append(next_value)

        # Map each value to its expected count of occurrences in the distribution
        expected_distribution = {}
        for value in random_values:
            count = random_values.count(value)
            if isinstance(field_type, SingleSelectFieldType):
                # For SingleSelect fields, the value should be the label of the
                # select option, not the entire select option object itself.
                key = value.value
            else:
                key = value
            expected_distribution[key] = count

        self.test_fields.append(field)
        self.random_values[field] = random_values
        self.expected_distributions[field] = expected_distribution

    def test_view_distribution_aggregation(self, data_fixture):
        user = data_fixture.create_user()
        table = data_fixture.create_database_table(user=user)

        # Create one field for each compatible field type and some random values for
        # each field. Then build a dict that contains the expected distribution given
        # the random values.
        text_field = data_fixture.create_text_field(table=table)
        self.create_random_values_and_expected_distributions(text_field)

        long_text_field = data_fixture.create_long_text_field(table=table)
        self.create_random_values_and_expected_distributions(long_text_field)

        url_field = data_fixture.create_url_field(table=table)
        self.create_random_values_and_expected_distributions(url_field)

        number_field = data_fixture.create_number_field(table=table)
        self.create_random_values_and_expected_distributions(number_field)

        rating_field = data_fixture.create_rating_field(table=table)
        self.create_random_values_and_expected_distributions(rating_field)

        date_field = data_fixture.create_date_field(table=table)
        self.create_random_values_and_expected_distributions(date_field)

        email_field = data_fixture.create_email_field(table=table)
        self.create_random_values_and_expected_distributions(email_field)

        phone_number_field = data_fixture.create_phone_number_field(table=table)
        self.create_random_values_and_expected_distributions(phone_number_field)

        duration_field = data_fixture.create_duration_field(table=table)
        self.create_random_values_and_expected_distributions(duration_field)

        boolean_field = data_fixture.create_boolean_field(table=table)
        self.create_random_values_and_expected_distributions(boolean_field)

        single_select_field = data_fixture.create_single_select_field(table=table)
        data_fixture.create_select_option(field=single_select_field)
        data_fixture.create_select_option(field=single_select_field)
        data_fixture.create_select_option(field=single_select_field)
        self.create_random_values_and_expected_distributions(single_select_field)

        # Create an iterable where every item represents the values of a row
        rows_values = zip(*[self.random_values[field] for field in self.test_fields])
        # Create a list of field names to reference them by
        field_names = [f"field_{field.id}" for field in self.test_fields]
        # Insert all row values into the table
        model = table.get_model()
        for row_values in rows_values:
            model.objects.create(
                **{
                    field_name: value
                    for field_name, value in zip(field_names, row_values)
                }
            )

        # After creating all the regular fields and inserting values for them, we
        # create these Formula fields that simply mirror the values of some of the
        # previously created fields. That means their distribution results should
        # match those of the fields they mirror.
        text_formula_field = data_fixture.create_formula_field(
            table=table, formula=f"field('{text_field.name}')"
        )
        number_formula_field = data_fixture.create_formula_field(
            table=table, formula=f"field('{number_field.name}')"
        )
        date_formula_field = data_fixture.create_formula_field(
            table=table, formula=f"field('{date_field.name}')"
        )
        boolean_formula_field = data_fixture.create_formula_field(
            table=table, formula=f"field('{boolean_field.name}')"
        )

        # Calculate the distribution aggregation of all fields in self.test_fields
        # and also the four formula fields
        grid_view = data_fixture.create_grid_view(table=table)
        result = ViewHandler().get_field_aggregations(
            user,
            grid_view,
            [(field, "distribution") for field in self.test_fields]
            + [
                (text_formula_field, "distribution"),
                (number_formula_field, "distribution"),
                (date_formula_field, "distribution"),
                (boolean_formula_field, "distribution"),
            ],
        )

        # Verify the distribution results for each field in test_fields
        for field in self.test_fields:
            for value, count in result[f"field_{field.id}"]:
                assert self.expected_distributions[field].get(value) == count

        # Verify that the text formula field distribution matches
        # the text field distribution:
        for value, count in result[f"field_{text_formula_field.id}"]:
            assert self.expected_distributions[text_field].get(value) == count

        # Verify that the number formula field distribution matches
        # the number field distribution:
        for value, count in result[f"field_{number_formula_field.id}"]:
            assert self.expected_distributions[number_field].get(value) == count

        # Verify that the date formula field distribution matches
        # the date field distribution:
        for value, count in result[f"field_{date_formula_field.id}"]:
            assert self.expected_distributions[date_field].get(value) == count

        # Verify that the boolean formula field distribution matches
        # the boolean field distribution:
        for value, count in result[f"field_{boolean_formula_field.id}"]:
            assert self.expected_distributions[boolean_field].get(value) == count
