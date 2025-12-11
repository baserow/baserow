from typing import Optional

from django.core.exceptions import ValidationError

import pytz

from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_datetime,
    ensure_numeric,
    ensure_object,
    ensure_string,
)


class BaserowRuntimeFormulaArgumentType:
    def __init__(self, optional: Optional[bool] = False):
        self.optional = optional

    def test(self, value):
        return True

    def parse(self, value):
        return value


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
            ensure_boolean(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_boolean(value)


class TimezoneBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        if not isinstance(value, str):
            return False

        return value in pytz.all_timezones

    def parse(self, value):
        return ensure_string(value)


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
