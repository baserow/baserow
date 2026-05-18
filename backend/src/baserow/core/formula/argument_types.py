from datetime import timedelta
from typing import Optional

from django.core.exceptions import ValidationError

import pytz

from baserow.core.formula.utils.date import (
    is_valid_datetime_format,
)
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_datetime,
    ensure_duration,
    ensure_numeric,
    ensure_object,
    ensure_string,
)

VALID_THOUSAND_SEPARATORS = {",", ".", " ", ""}
VALID_DECIMAL_SEPARATORS = {",", "."}


class BaserowRuntimeFormulaArgumentType:
    def __init__(self, optional: Optional[bool] = False):
        self.optional = optional

    def test(self, value):
        return True

    def parse(self, value):
        return value

    def get_error_message(self, value) -> Optional[str]:
        """
        This function should return a specific human-friendly error message
        if the value for the type is invalid.

        Defaults to returning None.
        """

        return None


class NumberBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def __init__(self, *args, **kwargs):
        self.cast_to_int = kwargs.pop("cast_to_int", False)
        self.cast_to_float = kwargs.pop("cast_to_float", False)
        super().__init__(*args, **kwargs)

    def test(self, value):
        try:
            ensure_numeric(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        value = ensure_numeric(value)
        if self.cast_to_int:
            return int(value)
        elif self.cast_to_float:
            return float(value)
        else:
            return value


class TextBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_string(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_string(value)


class DateTimeBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_datetime(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_datetime(value)


class DictBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_object(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_object(value)


class BooleanBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_boolean(value, False)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_boolean(value, False)


class TimezoneBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        if not isinstance(value, str):
            return False

        return value in pytz.all_timezones

    def parse(self, value):
        return ensure_string(value)

    def get_error_message(self, value) -> Optional[str]:
        return (
            f"'{value}' is not a valid timezone. "
            f"Please use a valid IANA timezone name "
            f"(e.g. 'Europe/Amsterdam')."
        )


class AnyBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        return True

    def parse(self, value):
        return value


class ArrayOfNumbersBaserowRuntimeFormulaArgumentType(
    BaserowRuntimeFormulaArgumentType
):
    def test(self, value):
        try:
            value = ensure_array(value)
        except ValidationError:
            return False

        for item in value:
            try:
                ensure_numeric(item)
            except ValidationError:
                return False

        return True

    def parse(self, value):
        value = ensure_array(value)
        return [ensure_numeric(item) for item in value]


class ThousandSeparatorBaserowRuntimeFormulaArgumentType(
    BaserowRuntimeFormulaArgumentType
):
    def test(self, value):
        if not isinstance(value, str):
            return False
        return value in VALID_THOUSAND_SEPARATORS

    def parse(self, value):
        return ensure_string(value)

    def get_error_message(self, value) -> Optional[str]:
        return (
            f"'{value}' is not a valid thousand separator. "
            f"Valid options are: ',', '.', ' ', or '' (empty string)."
        )


class DecimalSeparatorBaserowRuntimeFormulaArgumentType(
    BaserowRuntimeFormulaArgumentType
):
    def test(self, value):
        if not isinstance(value, str):
            return False
        return value in VALID_DECIMAL_SEPARATORS

    def parse(self, value):
        return ensure_string(value)

    def get_error_message(self, value) -> Optional[str]:
        return (
            f"'{value}' is not a valid decimal separator. "
            f"Valid options are: ',' or '.'."
        )


class TimedeltaBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        return isinstance(value, timedelta)

    def parse(self, value):
        return value


class DurationBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_duration(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_duration(value)

    def get_error_message(self, value) -> Optional[str]:
        return (
            f"'{value}' is not a valid duration. "
            f"Expected format: '<number> <unit>', e.g. '1 day', '2 hours'."
        )


class DatetimeFormatBaserowRuntimeFormulaArgumentType(
    BaserowRuntimeFormulaArgumentType
):
    def test(self, value):
        return is_valid_datetime_format(value)

    def parse(self, value):
        return ensure_string(value)

    def get_error_message(self, value) -> Optional[str]:
        return (
            f"'{value}' is not a valid datetime format. "
            f"Examples: 'YYYY-MM-DD' or 'DD/MM/YYYY HH:mm:ss'."
        )
