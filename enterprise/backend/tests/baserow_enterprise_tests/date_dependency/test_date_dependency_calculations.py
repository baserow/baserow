from datetime import date, timedelta

from django.utils.dateparse import parse_date

import pytest

from baserow_enterprise.date_dependency.field_rule_types import (
    NO_VALUE,
    DateDependencyCalculator,
    DateValues,
)


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

    def __eq__(self, other):
        return self is other


INVALID = object()

dep = FakeDateDependency()


def test_date_values_fields_api():
    dv = DateValues(dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=2)]))
    dv2 = DateValues(dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=2)]))

    dv3 = DateValues(dep, *prep_values(["2025-01-01", "2025-01-03", timedelta(days=3)]))

    dv4 = DateValues(dep, *prep_values([None, NO_VALUE, "invalid"]))

    assert dv == dv2
    assert dv != dv3

    assert dv.to_dict() == {
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 1, 3),
        "duration": timedelta(days=2),
    }
    assert dv.is_valid()
    assert dv.has_valid_values()
    assert dv.get_none_fields() == []
    assert dv.get_no_values_fields() == []
    assert dv.get_values_fields() == ["start_date", "end_date", "duration"]
    assert dv.get_changed_fields() == ["start_date", "end_date", "duration"]

    assert dv4.to_dict() == {
        "start_date": None,
        "end_date": NO_VALUE,
        "duration": "invalid",
    }
    assert not dv4.is_valid()
    assert not dv4.has_valid_values()
    assert dv4.get_none_fields() == ["start_date"]
    assert dv4.get_no_values_fields() == ["end_date"]
    assert dv4.get_values_fields() == ["duration"]
    assert dv4.get_changed_fields() == ["start_date", "duration"]

    assert dv.get("start_date") == date(2025, 1, 1)
    assert dv.get("end_date") == date(2025, 1, 3)
    assert dv.get("duration") == timedelta(days=2)
    with pytest.raises(ValueError):
        dv.get("invalid")


@pytest.mark.parametrize(
    "old_values,new_values,expected_result",
    [
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
            (
                False,
                False,
                False,
            ),
        ),
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
                True,
                True,
                False,
            ),
        ),
        (
            (
                None,
                None,
                None,
            ),
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                False,
                False,
                False,
            ),
        ),
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                None,
                None,
                None,
            ),
            (
                True,
                True,
                True,
            ),
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
                True,
                True,
                False,
            ),
        ),
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
                True,
                True,
                False,
            ),
        ),
    ],
)
def test_date_dependency_calculator_field_changed(
    old_values, new_values, expected_result
):
    """
    Test if DateDependencyCalculator.field_changed() detects field value
    changes correctly.
    """

    old_values = DateValues(dep, *prep_values(old_values))
    new_values = DateValues(dep, *prep_values(new_values))

    calc = DateDependencyCalculator(old_values, new_values, False)
    out = []
    for fname in DateValues.FIELDS:
        changed = calc.field_changed(old_values.get(fname), new_values.get(fname))
        out.append(changed)
    assert tuple(out) == expected_result


def test_date_dependency_calculator_field_value():
    """
    Test if DateDependencyCalculator.field_value() returns correctly new or old value.
    """

    calc = DateDependencyCalculator(None, None, False)

    assert calc.field_value(NO_VALUE, NO_VALUE) == NO_VALUE
    assert calc.field_value(None, NO_VALUE) is None
    assert calc.field_value(NO_VALUE, None) is None
    assert calc.field_value("old", None) is None
    assert calc.field_value("old", NO_VALUE) == "old"
    assert calc.field_value("old", "new") == "new"


@pytest.mark.parametrize(
    "test_value,include_weekends,expected_result",
    [
        # 2025-01-01 - Wednesday
        # 2025-01-03 - Wednesday
        # 2025-01-04 - Saturday
        # 2025-01-05 - Sunday
        # 2025-01-06 - Monday
        (
            ["2025-01-01", "2025-01-04", timedelta(days=3)],
            False,
            ["2025-01-01", "2025-01-04", timedelta(days=3)],
        ),
        (
            ["2025-01-01", "2025-01-03", timedelta(days=2)],
            False,
            ["2025-01-01", "2025-01-03", timedelta(days=2)],
        ),
        (
            ["2025-01-01", "2025-01-04", timedelta(days=3)],
            True,
            ["2025-01-01", "2025-01-06", timedelta(days=5)],
        ),
        (
            ["2025-01-01", "2025-01-03", timedelta(days=2)],
            True,
            ["2025-01-01", "2025-01-03", timedelta(days=2)],
        ),
        (
            ["2025-01-01", None, timedelta(days=4)],
            True,
            ["2025-01-01", None, timedelta(days=4)],
        ),
        (
            ["2025-01-01", None, timedelta(days=4)],
            False,
            ["2025-01-01", None, timedelta(days=4)],
        ),
    ],
)
def test_date_dependency_adjust_end_date(test_value, include_weekends, expected_result):
    """
    Test if DaeDependencyCalculator will correctly shift end date and duration if
    include_weekends flag is set and end date is on weekend.
    """

    calc = DateDependencyCalculator(None, None, include_weekends)

    input_value = DateValues(dep, *prep_values(test_value))
    expected = DateValues(dep, *prep_values(expected_result))
    calc.adjust_end_date(input_value)
    assert input_value.to_dict() == expected.to_dict()


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
            False,
        ),
        # duration is not set at all
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
                NO_VALUE,
            ),
            False,
        ),
        # set values, recalcualte all
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
                timedelta(days=9),
            ),
            False,
        ),
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-06",
                timedelta(days=5),
            ),
            True,
        ),
        (
            (
                NO_VALUE,
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=4),
            ),
            False,
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
                None,
            ),
            (
                "2020-01-01",
                "2020-01-10",
                timedelta(days=9),
            ),
            False,
        ),
        # recalculate duration when it's empty
        (
            (
                "2020-01-01",
                "2020-01-05",
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
                timedelta(days=4),
            ),
            False,
        ),
        (
            (
                "2020-01-01",
                "2020-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-06",
                timedelta(days=5),
            ),
            True,
        ),
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
                timedelta(days=4),
            ),
            False,
        ),
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
                "2025-01-06",
                timedelta(days=5),
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
                "2025-01-05",
                timedelta(days=5),
            ),
            (None, "2025-01-05", None),
            False,
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
            False,
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
            False,
        ),
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
            False,
        ),
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
                "2025-01-02",
                timedelta(days=1),
            ),
            False,
        ),
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
                "2025-01-02",
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
                timedelta(days=1),
            ),
            False,
        ),
        # even if include_weekend flag is set, this won't be adjusted, because
        # we set end date manually.
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
                timedelta(days=1),
            ),
            True,
        ),
        # recalculate duration even if it's set
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=4),
            ),
            False,
        ),
        (
            (
                "2025-01-01",
                "2025-01-05",
                timedelta(days=5),
            ),
            (
                "2025-01-01",
                "2025-01-05",
                None,
            ),
            (
                "2025-01-01",
                "2025-01-06",
                timedelta(days=5),
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
            False,
        ),
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
                "2025-01-02",
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2025-01-02",
                "2025-01-04",
                timedelta(days=2),
            ),
            False,
        ),
        (
            (
                "2025-01-01",
                "2025-01-03",
                timedelta(days=2),
            ),
            (
                "2025-01-02",
                NO_VALUE,
                NO_VALUE,
            ),
            (
                "2025-01-02",
                "2025-01-06",
                timedelta(days=4),
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
                timedelta(days=3),
            ),
            False,
        ),
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
                timedelta(days=3),
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

    old_val = DateValues(dep, *prep_values(old_values))
    new_val = DateValues(dep, *prep_values(new_values))
    if expected_result:
        expected = DateValues(dep, *prep_values(expected_result))
    else:
        expected = expected_result

    calc = DateDependencyCalculator(old_val, new_val, include_weekends)

    assert calc._calculate() == expected
