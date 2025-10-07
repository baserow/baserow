from copy import copy, deepcopy
from datetime import date, timedelta

from django.utils.dateparse import parse_date

import pytest

from baserow_enterprise.date_dependency.calculations import (
    DateCalculator,
    DateDependencyCalculator,
    DateValues,
    adjust_child,
    adjust_parent,
    calculate_date_dependency_end,
    calculate_date_dependency_start,
)
from baserow_enterprise.date_dependency.constants import NO_VALUE
from baserow_enterprise.date_dependency.models import DateDependency


def prep_values(args):
    return [(parse_date(arg) or arg) if isinstance(arg, str) else arg for arg in args]


class FakeField:
    def __init__(self, field_name):
        self.field_name = field_name
        self.db_column = field_name


class FakeRow:
    def __init__(self, start_date, end_date, duration):
        self.start_date = start_date
        self.end_date = end_date
        self.duration = duration


class FakeDateDependency:
    start_date_field = FakeField("start_date")
    end_date_field = FakeField("end_date")
    duration_field = FakeField("duration")
    dependency_linrow_field = FakeField("linkrow_field")
    include_weekends: bool = True

    def __init__(self, include_weekends=True):
        self.include_weekends = include_weekends
        self.buffer_is_none = False
        self.buffer_is_flexible = True
        self.buffer_is_fixed = False
        self.dependency_buffer = timedelta(0)

    def __eq__(self, other):
        return self is other


INVALID = object()

dep = FakeDateDependency()


def test_date_values_fields_api():
    dv = DateValues(dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=3)]))
    dv2 = DateValues(dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=3)]))
    dv3 = DateValues(dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=4)]))

    # invalid value types
    dv4 = DateValues(dep, *prep_values([None, NO_VALUE, "invalid"]))
    # end date before start date
    dv5 = DateValues(dep, *prep_values(["2025-01-20", "2025-01-03", timedelta(days=4)]))
    # negative duration
    dv6 = DateValues(
        dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=-3)])
    )
    # overflow
    dv7 = DateValues(
        dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=100000000)])
    )
    date_values = [dv, dv2, dv3, dv4, dv5, dv6, dv7]

    assert dv == dv2
    assert dv != dv3

    assert dv.to_dict() == {
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 1, 3),
        "duration": timedelta(days=3),
    }
    assert dv.is_valid()
    assert dv.has_valid_value_types()
    assert dv.get_none_fields() == []
    assert dv.get_no_values_fields() == []
    assert dv.get_values_fields() == ["start_date", "end_date", "duration"]
    assert dv.get_set_fields() == ["start_date", "end_date", "duration"]

    assert dv.get("start_date") == date(2025, 1, 1)
    assert dv.get("end_date") == date(2025, 1, 3)
    assert dv.get("duration") == timedelta(days=3)
    with pytest.raises(ValueError):
        dv.get("invalid")

    assert dv4.to_dict() == {
        "start_date": None,
        "end_date": NO_VALUE,
        "duration": "invalid",
    }
    assert not dv4.is_valid()
    assert not dv4.has_valid_value_types()
    assert dv4.get_none_fields() == ["start_date"]
    assert dv4.get_no_values_fields() == ["end_date"]
    assert dv4.get_values_fields() == ["duration"]
    assert dv4.get_set_fields() == ["start_date", "duration"]

    assert not dv5.is_valid()
    assert dv5.has_valid_value_types()
    assert dv5.get_none_fields() == []
    assert dv5.get_no_values_fields() == []
    assert dv5.get_values_fields() == ["start_date", "end_date", "duration"]

    assert not dv6.is_valid()
    assert dv6.has_valid_value_types()
    assert dv6.get_none_fields() == []
    assert dv6.get_no_values_fields() == []
    assert dv6.get_values_fields() == ["start_date", "end_date", "duration"]

    assert not dv7.is_valid()

    for date_value in date_values:
        assert date_value.to_dict() == copy(date_value).to_dict()


def test_date_dependency_calculator_field_value():
    """
    Test if DateCalculator.field_value() returns correctly new or old value.
    """

    calc = DateCalculator(None, None, False)

    assert calc.field_value(NO_VALUE, NO_VALUE) == NO_VALUE
    assert calc.field_value(None, NO_VALUE) is None
    assert calc.field_value(NO_VALUE, None) is None
    assert calc.field_value("old", None) is None
    assert calc.field_value("old", NO_VALUE) == "old"
    assert calc.field_value("old", "new") == "new"


@pytest.mark.parametrize(
    "old_values,new_values,expected_result,include_weekends",
    [
        # nothing changed, no value
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            None,
            True,
        ),
        # duration not recaclulated, because all three values are changed
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                None,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                None,
            ),
            True,
        ),
        # Duration is not set at all, so it will be recalculated.
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                NO_VALUE,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                timedelta(days=10),
            ),
            True,
        ),
        #
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                NO_VALUE,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            True,
        ),
        (
            (
                None,
                None,
                None,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                NO_VALUE,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                timedelta(days=10),
            ),
            True,
        ),
        # start/duration provided, end calculated
        (
            (
                None,
                None,
                None,
            ),
            ("2020-01-01", NO_VALUE, timedelta(days=10)),
            (
                "2020-01-01",
                "2020-01-10",
                timedelta(days=10),
            ),
            True,
        ),
        # No recalculation if all three values are set
        (
            (
                "2020-01-01",
                "2020-01-02",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            True,
        ),
        # start with invalid dates, but no recalculation, as we set all values
        (
            (
                "2025-01-01",
                "2025-01-01",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            True,
        ),
        # reset duration when start date is nullified
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            (
                None,
                "2025-01-05",
                timedelta(days=5),
            ),
            (None, "2025-01-05", None),
            True,
        ),
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            (
                None,
                NO_VALUE,
                NO_VALUE,
            ),
            (None, "2025-01-05", None),
            True,
        ),
        # setting just duration to None sets duration value to None
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            (
                NO_VALUE,
                NO_VALUE,
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            True,
        ),
        # setting just one values to None sets that value to None
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            (
                NO_VALUE,
                None,
                NO_VALUE,
            ),
            (
                "2025-01-01",
                None,
                timedelta(days=5),
            ),
            True,
        ),
        # incomplete old state and update with one value results in a recalculation
        (
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                NO_VALUE,
                NO_VALUE,
                timedelta(days=1),
            ),
            (
                "2025-01-01",
                "2025-01-01",
                timedelta(days=1),
            ),
            True,
        ),
        (
            (
                "2025-01-03",
                None,
                timedelta(days=1),
            ),
            (
                NO_VALUE,
                "2025-01-04",
                NO_VALUE,
            ),
            (
                "2025-01-03",
                "2025-01-04",
                timedelta(days=2),
            ),
            True,
        ),
        # duration set to None explicitly
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=3),
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            True,
        ),
        # invalid update results in invalid value
        (
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=1),
            ),
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=1),
            ),
            True,
        ),
        # update start date will recalculate a row
        (
            (
                "2025-01-01",
                "2025-01-03",
                timedelta(days=2),
            ),
            (
                "2025-01-06",
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2025-01-06",
                "2025-01-07",
                timedelta(days=2),
            ),
            True,
        ),
        # update end date will recalculate a row
        (
            (
                "2025-01-01",
                "2025-01-03",
                timedelta(days=2),
            ),
            (
                NO_VALUE,
                "2025-01-04",
                NO_VALUE,
            ),
            (
                "2025-01-01",
                "2025-01-04",
                timedelta(days=4),
            ),
            True,
        ),
        # we move end_date down, but after start_date, so this should decrease
        # duration value.
        (
            (
                "2025-01-01",
                "2025-01-06",
                timedelta(days=6),
            ),
            (
                NO_VALUE,
                "2025-01-04",
                NO_VALUE,
            ),
            (
                "2025-01-01",
                "2025-01-04",
                timedelta(days=4),
            ),
            True,
        ),
        # we move end_date before start_date, so this should result in start_date shift
        # down by duration value
        (
            (
                "2025-02-01",
                "2025-02-06",
                timedelta(days=6),
            ),
            (
                NO_VALUE,
                "2025-01-30",
                NO_VALUE,
            ),
            (
                "2025-01-25",
                "2025-01-30",
                timedelta(days=6),
            ),
            True,
        ),
        # duration overflow
        (
            (
                "2025-01-01",
                "2025-01-06",
                None,
            ),
            (
                NO_VALUE,
                NO_VALUE,
                timedelta(days=9999999),
            ),
            (
                "2025-01-01",
                "2025-01-06",
                timedelta(days=9999999),
            ),
            True,
        ),
    ],
)
def test_date_dependency_calculations(
    old_values, new_values, expected_result, include_weekends
):
    """
    Check if specific old/new state values are resulting in expected result.

    Note, API can receive one or more fields update. Any field that is
    not updated by API should be marked with NO_VALUE.
    """

    dep = FakeDateDependency(include_weekends=include_weekends)

    old_val = DateValues(dep, *prep_values(old_values))
    new_val = DateValues(dep, *prep_values(new_values))
    if expected_result:
        expected = DateValues(dep, *prep_values(expected_result))
    else:
        expected = expected_result

    calc = DateCalculator(old_val, new_val, include_weekends)
    result = calc._calculate()
    assert result == expected


# calendar:
# 2024-12-29 - Sunday *
# 2024-12-30 - Monday
# 2024-12-31 - Tuesday
# 2025-01-01 - Wednesday
# 2025-01-02 - Thursday
# 2025-01-03 - Friday
# 2025-01-04 - Saturday *
# 2025-01-05 - Sunday *
# 2025-01-06 - Monday
# ..
# 2025-01-10 - Saturday
# 2025-01-11 - Sunday
# ..
# 2025-01-17 - Saturday
# 2025-01-18 - Sunday
# ..
# duration includes extra day
@pytest.mark.parametrize(
    "end_date,duration,expected_start_date,include_weekends",
    [
        (
            "2025-01-05",
            timedelta(days=0),
            None,
            True,
        ),
        (
            "2025-01-05",
            timedelta(days=1),
            "2025-01-05",
            True,
        ),
        (
            "2025-01-13",
            timedelta(days=9),
            "2025-01-05",
            True,
        ),
    ],
)
def test_calculate_start_date(
    end_date, duration, expected_start_date, include_weekends
):
    class FakeDependency:
        def __init__(self, include_weekends):
            self.include_weekends = include_weekends

    dep = FakeDependency(include_weekends)

    input_val = DateValues(
        dep, start_date=None, end_date=parse_date(end_date), duration=duration
    )
    output = calculate_date_dependency_start(input_val)
    if expected_start_date:
        expected_start_date = parse_date(expected_start_date)
    assert output.start_date == expected_start_date


@pytest.mark.parametrize(
    "start_date,duration,expected_end_date,include_weekends",
    [
        (
            "2025-01-05",
            timedelta(days=0),
            None,
            True,
        ),
        (
            "2025-01-05",
            timedelta(days=1),
            "2025-01-05",
            True,
        ),
        (
            "2025-01-05",
            timedelta(days=8),
            "2025-01-12",
            True,
        ),
        (
            "2025-01-10",
            timedelta(days=8),
            "2025-01-17",
            True,
        ),
    ],
)
def test_calculate_end_date(start_date, duration, expected_end_date, include_weekends):
    class FakeDependency:
        def __init__(self, include_weekends):
            self.include_weekends = include_weekends

    dep = FakeDependency(include_weekends)

    input_val = DateValues(
        dep, end_date=None, start_date=parse_date(start_date), duration=duration
    )
    output = calculate_date_dependency_end(input_val)
    if expected_end_date:
        expected_end_date = parse_date(expected_end_date)
    assert output.end_date == expected_end_date


@pytest.mark.parametrize(
    "parent_data,child_data,expected_adjusted,expected_parent_data",
    [
        # simple shift before start of a child
        (
            (
                date(2025, 1, 15),
                date(2025, 1, 20),
                timedelta(days=6),
            ),
            (
                date(2025, 1, 11),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            True,
            (date(2025, 1, 5), date(2025, 1, 10), timedelta(days=6)),
        ),
        # missing start value, but this will be recalculated
        (
            (
                None,
                date(2025, 1, 20),
                timedelta(days=6),
            ),
            (
                date(2025, 1, 11),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            True,
            (date(2025, 1, 5), date(2025, 1, 10), timedelta(days=6)),
        ),
        # invalid values, no adjustment
        (
            (None, None, timedelta(days=1)),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            False,
            (None, None, timedelta(days=1)),
        ),
        # invalid values, no adjustment
        (
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            (None, None, timedelta(days=1)),
            False,
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
        ),
        # missing end date, no adjustment
        (
            (date(2025, 1, 10), None, timedelta(days=1)),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            False,
            (date(2025, 1, 10), None, timedelta(days=1)),
        ),
        # no overlap, no change
        (
            (
                date(2025, 1, 1),
                date(2025, 1, 5),
                timedelta(days=5),
            ),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            False,
            (date(2025, 1, 1), date(2025, 1, 5), timedelta(days=5)),
        ),
    ],
)
def test_calculate_parent(
    parent_data, child_data, expected_adjusted, expected_parent_data
):
    dep = DateDependency()
    dep.include_weekends = True
    parent = DateValues(dep, *parent_data)
    child = DateValues(dep, *child_data)
    expected_parent = DateValues(dep, *expected_parent_data)
    adjusted = adjust_parent(parent, child, dep)
    assert adjusted == expected_adjusted
    assert parent == expected_parent


@pytest.mark.parametrize(
    "parent_data,child_data,expected_adjusted,expected_child_data",
    [
        # simple shift before start of a child
        (
            (
                date(2025, 1, 10),
                date(2025, 1, 20),
                timedelta(days=10),
            ),
            (
                date(2025, 1, 10),
                date(2025, 1, 15),
                timedelta(days=6),
            ),
            True,
            (date(2025, 1, 21), date(2025, 1, 26), timedelta(days=6)),
        ),
        # child missing start date, not calculable
        (
            (
                date(2025, 1, 10),
                date(2025, 1, 20),
                timedelta(days=10),
            ),
            (
                None,
                date(2025, 1, 15),
                timedelta(days=5),
            ),
            False,
            (None, date(2025, 1, 15), timedelta(days=5)),
        ),
        # missing start value, but we can recalculate
        (
            (
                None,
                date(2025, 1, 20),
                timedelta(days=5),
            ),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            True,
            (
                date(2025, 1, 21),
                date(2025, 1, 30),
                timedelta(days=10),
            ),
        ),
        # invalid values, no adjustment
        (
            (None, None, timedelta(days=1)),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            False,
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
        ),
        # invalid values, no adjustment
        (
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            (None, None, timedelta(days=1)),
            False,
            (None, None, timedelta(days=1)),
        ),
        # missing end date, no adjustment
        (
            (date(2025, 1, 10), None, timedelta(days=1)),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            False,
            (date(2025, 1, 10), date(2025, 1, 25), timedelta(days=10)),
        ),
        # no overlap, no change
        (
            (
                date(2025, 1, 1),
                date(2025, 1, 5),
                timedelta(days=5),
            ),
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
            False,
            (
                date(2025, 1, 10),
                date(2025, 1, 25),
                timedelta(days=10),
            ),
        ),
    ],
)
def test_calculate_child(
    parent_data, child_data, expected_adjusted, expected_child_data
):
    dep = DateDependency()
    dep.include_weekends = True
    parent = DateValues(dep, *parent_data)
    child = DateValues(dep, *child_data)
    expected_child = DateValues(dep, *expected_child_data)
    adjusted = adjust_child(parent, child, dep)
    assert adjusted == expected_adjusted
    assert child == expected_child


def test_date_dependency_calc_cache():
    """
    Tests if row cache is used properly during deps calculations
    :return:
    """

    class FakeRow:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def __eq__(self, other):
            return self.__dict__ == other.__dict__

        def __repr__(self):
            return f"FakeRow({self.__dict__})"

    dep = FakeDateDependency()

    test_data = [
        (1, date(2025, 5, 1), date(2025, 5, 2), timedelta(days=2), []),
        (2, date(2025, 5, 1), date(2025, 5, 2), timedelta(days=2), [1]),
        (3, date(2025, 5, 1), date(2025, 5, 2), timedelta(days=2), [2]),
        (4, date(2025, 5, 1), date(2025, 5, 2), timedelta(days=2), [2]),
    ]
    expected_test_data = [
        (1, date(2025, 5, 1), date(2025, 5, 2), timedelta(days=2), []),
        (2, date(2025, 5, 3), date(2025, 5, 4), timedelta(days=2), [1]),
        (3, date(2025, 5, 5), date(2025, 5, 6), timedelta(days=2), [2]),
        (4, date(2025, 5, 5), date(2025, 5, 6), timedelta(days=2), [2]),
    ]

    rows_cache = {}
    expected_rows_cache = {}
    graph_paths = [[1, 2, 3], [1, 2, 4]]
    for row_id, start_date, end_date, duration, linked in test_data:
        row_obj = FakeRow(
            id=row_id,
            start_date=start_date,
            end_date=end_date,
            duration=duration,
            linkrow_field=[rows_cache.get(linked_id) for linked_id in linked],
        )
        rows_cache[row_id] = row_obj

    for row_id, start_date, end_date, duration, linked in expected_test_data:
        row_obj = FakeRow(
            id=row_id,
            start_date=start_date,
            end_date=end_date,
            duration=duration,
            linkrow_field=[expected_rows_cache.get(linked_id) for linked_id in linked],
        )
        expected_rows_cache[row_id] = row_obj

    deps_calculator = DateDependencyCalculator(row=rows_cache[1], rule=dep)
    deps_calculator.cache = deepcopy(rows_cache)
    deps_calculator.graph_paths = deepcopy(graph_paths)
    deps_calculator.populate_dependency_graph = lambda *args, **kwargs: None
    deps_calculator.calculate()
    assert deps_calculator.graph_paths == graph_paths
    assert set(deps_calculator.cache.keys()) == set(expected_rows_cache.keys())

    for row_id, row_obj in expected_rows_cache.items():
        assert deps_calculator.cache[row_id] == row_obj
    assert deps_calculator.visited == {2, 3, 4}
