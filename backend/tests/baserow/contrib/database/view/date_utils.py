from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta

from baserow.contrib.database.views.view_filters import (
    DateFilterOperators,
    DateIsAfterMultiStepFilterType,
    DateIsBeforeMultiStepFilterType,
    DateIsEqualMultiStepFilterType,
    DateIsNotEqualMultiStepFilterType,
    DateIsOnOrAfterMultiStepFilterType,
    DateIsOnOrBeforeMultiStepFilterType,
    DateIsWithinMultiStepFilterType,
)

# given today is 2024-05-24, please provide some datetime values for
# all the DateFilterOperators
FREEZED_TODAY = datetime(2024, 5, 24, 9, 30, 0, tzinfo=timezone.utc)

# fmt:off
TEST_MULTI_STEP_DATE_OPERATORS_DATETIMES = [
    FREEZED_TODAY - relativedelta(days=1),    # 0. yesterday
    FREEZED_TODAY,                            # 1. today
    FREEZED_TODAY + relativedelta(days=1),    # 2. tomorrow
    FREEZED_TODAY - relativedelta(weeks=1),   # 3. a week ago
    FREEZED_TODAY - relativedelta(months=1),  # 4. a month ago
    FREEZED_TODAY - relativedelta(years=1),   # 5. a year ago
    FREEZED_TODAY + relativedelta(weeks=1),   # 6. a week from now
    FREEZED_TODAY + relativedelta(months=1),  # 7. a month from now
    FREEZED_TODAY + relativedelta(years=1),   # 8. a year from now
]
# fmt:on

MNEMONIC_VALUES = {
    "-1d": 0,
    "now": 1,
    "+1d": 2,
    "-1w": 3,
    "-1m": 4,
    "-1y": 5,
    "+1w": 6,
    "+1m": 7,
    "+1y": 8,
}

# expected_results contains a list of the valid indexes of the
# TEST_MULTI_STEP_DATE_OPERATORS_DATETIMES that should be returned when the filter type
# and the operator is applied to the given dates
DATE_MULTI_STEP_OPERATOR_VALID_RESULTS = {
    DateIsEqualMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {"expected_results": ["-1d"]},
        DateFilterOperators.TODAY: {"expected_results": ["now"]},
        DateFilterOperators.TOMORROW: {"expected_results": ["+1d"]},
        DateFilterOperators.ONE_WEEK_AGO: {"expected_results": ["-1w"]},
        DateFilterOperators.ONE_MONTH_AGO: {"expected_results": ["-1m"]},
        DateFilterOperators.ONE_YEAR_AGO: {"expected_results": ["-1y"]},
        DateFilterOperators.THIS_WEEK: {"expected_results": ["-1d", "now", "+1d"]},
        DateFilterOperators.THIS_MONTH: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "+1w"]
        },
        DateFilterOperators.THIS_YEAR: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "+1w", "+1m"]
        },
        DateFilterOperators.NEXT_WEEK: {"expected_results": ["+1w"]},
        DateFilterOperators.NEXT_MONTH: {"expected_results": ["+1m"]},
        DateFilterOperators.NEXT_YEAR: {"expected_results": ["+1y"]},
        DateFilterOperators.NR_DAYS_AGO: {"expected_results": ["-1w"], "value": 7},
        DateFilterOperators.NR_WEEKS_AGO: {"expected_results": ["-1w"], "value": 1},
        DateFilterOperators.NR_MONTHS_AGO: {"expected_results": ["-1m"], "value": 1},
        DateFilterOperators.NR_YEARS_AGO: {"expected_results": ["-1y"], "value": 1},
        DateFilterOperators.NR_DAYS_FROM_NOW: {"expected_results": ["+1w"], "value": 7},
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": ["+1w"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": ["+1m"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": ["+1y"],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": ["now"],
            "value": "2024-05-24",
        },
    },
    DateIsNotEqualMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {
            "expected_results": ["now", "+1d", "-1w", "-1m", "-1y", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.TODAY: {
            "expected_results": ["-1d", "+1d", "-1w", "-1m", "-1y", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.TOMORROW: {
            "expected_results": ["-1d", "now", "-1w", "-1m", "-1y", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_WEEK_AGO: {
            "expected_results": ["-1d", "now", "+1d", "-1m", "-1y", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_MONTH_AGO: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1y", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_YEAR_AGO: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.THIS_WEEK: {
            "expected_results": ["-1w", "-1m", "-1y", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.THIS_MONTH: {
            "expected_results": ["-1y", "-1m", "+1m", "+1y"]
        },
        DateFilterOperators.THIS_YEAR: {"expected_results": ["-1y", "+1y"]},
        DateFilterOperators.NEXT_WEEK: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1m", "+1y"]
        },
        DateFilterOperators.NEXT_MONTH: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w", "+1y"]
        },
        DateFilterOperators.NEXT_YEAR: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w", "+1m"]
        },
        DateFilterOperators.NR_DAYS_AGO: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_AGO: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_AGO: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1y",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_AGO: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_DAYS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1m",
                "+1y",
            ],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
            ],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": [
                "-1d",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": "2024-05-24",
        },
    },
    DateIsBeforeMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {"expected_results": ["-1w", "-1m", "-1y"]},
        DateFilterOperators.TODAY: {"expected_results": ["-1d", "-1w", "-1m", "-1y"]},
        DateFilterOperators.TOMORROW: {
            "expected_results": ["-1d", "now", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.ONE_WEEK_AGO: {"expected_results": ["-1m", "-1y"]},
        DateFilterOperators.ONE_MONTH_AGO: {"expected_results": ["-1y"]},
        DateFilterOperators.ONE_YEAR_AGO: {"expected_results": []},
        DateFilterOperators.THIS_WEEK: {"expected_results": ["-1w", "-1m", "-1y"]},
        DateFilterOperators.THIS_MONTH: {"expected_results": ["-1m", "-1y"]},
        DateFilterOperators.THIS_YEAR: {"expected_results": ["-1y"]},
        DateFilterOperators.NEXT_WEEK: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.NEXT_MONTH: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w"]
        },
        DateFilterOperators.NEXT_YEAR: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w", "+1m"]
        },
        DateFilterOperators.NR_DAYS_AGO: {
            "expected_results": ["-1m", "-1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_AGO: {
            "expected_results": ["-1m", "-1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_AGO: {"expected_results": ["-1y"], "value": 1},
        DateFilterOperators.NR_YEARS_AGO: {"expected_results": [], "value": 1},
        DateFilterOperators.NR_DAYS_FROM_NOW: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
            ],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": ["-1d", "-1w", "-1m", "-1y"],
            "value": "2024-05-24",
        },
    },
    DateIsOnOrBeforeMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {
            "expected_results": ["-1d", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.TODAY: {
            "expected_results": ["-1d", "now", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.TOMORROW: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.ONE_WEEK_AGO: {"expected_results": ["-1w", "-1m", "-1y"]},
        DateFilterOperators.ONE_MONTH_AGO: {"expected_results": ["-1m", "-1y"]},
        DateFilterOperators.ONE_YEAR_AGO: {"expected_results": ["-1y"]},
        DateFilterOperators.THIS_WEEK: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.THIS_MONTH: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w"]
        },
        DateFilterOperators.THIS_YEAR: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w", "+1m"]
        },
        DateFilterOperators.NEXT_WEEK: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w"]
        },
        DateFilterOperators.NEXT_MONTH: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w", "+1m"]
        },
        DateFilterOperators.NEXT_YEAR: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
                "+1y",
            ]
        },
        DateFilterOperators.NR_DAYS_AGO: {
            "expected_results": ["-1w", "-1m", "-1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_AGO: {
            "expected_results": ["-1w", "-1m", "-1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_AGO: {
            "expected_results": ["-1m", "-1y"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_AGO: {
            "expected_results": ["-1y"],
            "value": 1,
        },
        DateFilterOperators.NR_DAYS_FROM_NOW: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "-1m", "-1y", "+1w"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": [
                "-1d",
                "now",
                "+1d",
                "-1w",
                "-1m",
                "-1y",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": ["-1d", "now", "-1w", "-1m", "-1y"],
            "value": "2024-05-24",
        },
    },
    DateIsAfterMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {
            "expected_results": ["now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.TODAY: {"expected_results": ["+1d", "+1w", "+1m", "+1y"]},
        DateFilterOperators.TOMORROW: {"expected_results": ["+1w", "+1m", "+1y"]},
        DateFilterOperators.ONE_WEEK_AGO: {
            "expected_results": ["-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_MONTH_AGO: {
            "expected_results": ["-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_YEAR_AGO: {
            "expected_results": ["-1m", "-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.THIS_WEEK: {"expected_results": ["+1w", "+1m", "+1y"]},
        DateFilterOperators.THIS_MONTH: {"expected_results": ["+1m", "+1y"]},
        DateFilterOperators.THIS_YEAR: {"expected_results": ["+1y"]},
        DateFilterOperators.NEXT_WEEK: {"expected_results": ["+1m", "+1y"]},
        DateFilterOperators.NEXT_MONTH: {"expected_results": ["+1y"]},
        DateFilterOperators.NEXT_YEAR: {"expected_results": []},
        DateFilterOperators.NR_DAYS_AGO: {
            "expected_results": ["-1d", "now", "+1d", "+1w", "+1m", "+1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_AGO: {
            "expected_results": ["-1d", "now", "+1d", "+1w", "+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_AGO: {
            "expected_results": ["-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_AGO: {
            "expected_results": [
                "-1m",
                "-1w",
                "-1d",
                "now",
                "+1d",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_DAYS_FROM_NOW: {
            "expected_results": ["+1m", "+1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": ["+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": ["+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": [],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": ["+1d", "+1w", "+1m", "+1y"],
            "value": "2024-05-24",
        },
    },
    DateIsOnOrAfterMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {
            "expected_results": ["-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.TODAY: {
            "expected_results": ["now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.TOMORROW: {
            "expected_results": ["+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_WEEK_AGO: {
            "expected_results": ["-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_MONTH_AGO: {
            "expected_results": ["-1m", "-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.ONE_YEAR_AGO: {
            "expected_results": [
                "-1y",
                "-1m",
                "-1w",
                "-1d",
                "now",
                "+1d",
                "+1w",
                "+1m",
                "+1y",
            ]
        },
        DateFilterOperators.THIS_WEEK: {
            "expected_results": ["-1d", "now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.THIS_MONTH: {
            "expected_results": ["-1d", "now", "+1d", "-1w", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.THIS_YEAR: {
            "expected_results": ["-1d", "now", "+1d", "-1m", "-1w", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.NEXT_WEEK: {"expected_results": ["+1w", "+1m", "+1y"]},
        DateFilterOperators.NEXT_MONTH: {"expected_results": ["+1m", "+1y"]},
        DateFilterOperators.NEXT_YEAR: {"expected_results": ["+1y"]},
        DateFilterOperators.NR_DAYS_AGO: {
            "expected_results": ["-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_AGO: {
            "expected_results": ["-1w", "-1d", "now", "+1d", "+1w", "+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_AGO: {
            "expected_results": [
                "-1m",
                "-1w",
                "-1d",
                "now",
                "+1d",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_AGO: {
            "expected_results": [
                "-1y",
                "-1m",
                "-1w",
                "-1d",
                "now",
                "+1d",
                "+1w",
                "+1m",
                "+1y",
            ],
            "value": 1,
        },
        DateFilterOperators.NR_DAYS_FROM_NOW: {
            "expected_results": ["+1w", "+1m", "+1y"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": ["+1w", "+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": ["+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": ["+1y"],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": ["now", "+1d", "+1w", "+1m", "+1y"],
            "value": "2024-05-24",
        },
    },
    DateIsWithinMultiStepFilterType.type: {
        DateFilterOperators.YESTERDAY: {"expected_results": ["-1d", "now"]},
        DateFilterOperators.TOMORROW: {"expected_results": ["now", "+1d"]},
        DateFilterOperators.ONE_WEEK_AGO: {"expected_results": ["-1d", "now", "-1w"]},
        DateFilterOperators.ONE_MONTH_AGO: {
            "expected_results": ["-1d", "now", "-1w", "-1m"]
        },
        DateFilterOperators.ONE_YEAR_AGO: {
            "expected_results": ["-1d", "now", "-1w", "-1m", "-1y"]
        },
        DateFilterOperators.THIS_WEEK: {"expected_results": ["now", "+1d"]},
        DateFilterOperators.THIS_MONTH: {"expected_results": ["now", "+1d", "+1w"]},
        DateFilterOperators.THIS_YEAR: {
            "expected_results": ["now", "+1d", "+1w", "+1m"]
        },
        DateFilterOperators.NEXT_WEEK: {"expected_results": ["now", "+1d", "+1w"]},
        DateFilterOperators.NEXT_MONTH: {
            "expected_results": ["now", "+1d", "+1w", "+1m"]
        },
        DateFilterOperators.NEXT_YEAR: {
            "expected_results": ["now", "+1d", "+1w", "+1m", "+1y"]
        },
        DateFilterOperators.NR_DAYS_FROM_NOW: {
            "expected_results": ["now", "+1d", "+1w"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_FROM_NOW: {
            "expected_results": ["now", "+1d", "+1w"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_FROM_NOW: {
            "expected_results": ["now", "+1d", "+1w", "+1m"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_FROM_NOW: {
            "expected_results": ["now", "+1d", "+1w", "+1m", "+1y"],
            "value": 1,
        },
        DateFilterOperators.NR_DAYS_AGO: {
            "expected_results": ["now", "-1d", "-1w"],
            "value": 7,
        },
        DateFilterOperators.NR_WEEKS_AGO: {
            "expected_results": ["now", "-1d", "-1w"],
            "value": 1,
        },
        DateFilterOperators.NR_MONTHS_AGO: {
            "expected_results": ["now", "-1d", "-1w", "-1m"],
            "value": 1,
        },
        DateFilterOperators.NR_YEARS_AGO: {
            "expected_results": ["now", "-1d", "-1w", "-1m", "-1y"],
            "value": 1,
        },
        DateFilterOperators.EXACT_DATE: {
            "expected_results": ["now", "+1d"],
            "value": "2024-05-25",
        },
    },
}
