from enum import Enum


class NoValueSentinel:
    """
    Helper class to mark missing values.
    """


NO_VALUE = NoValueSentinel()


class DateDependencyFieldNames(str, Enum):
    """
    A list of field names used by date dependency rule.
    """

    START_DATE = "start_date"
    END_DATE = "end_date"
    DURATION = "duration"
