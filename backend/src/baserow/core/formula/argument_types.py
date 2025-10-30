from django.core.exceptions import ValidationError

from baserow.core.formula.validator import (
    ensure_boolean,
    ensure_datetime,
    ensure_numeric,
    ensure_object,
    ensure_string,
)


class BaserowRuntimeFormulaArgumentType:
    def test(self, value):
        return True

    def parse(self, value):
        return value


class NumberBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_numeric(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_numeric(value)


class TextBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        try:
            ensure_string(value)
            return True
        except ValidationError:
            return False

    def parse(self, value):
        return ensure_string(value)


class AddableBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        return hasattr(value, "__add__")

    def parse(self, value):
        return value


class SubtractableBaserowRuntimeFormulaArgumentType(BaserowRuntimeFormulaArgumentType):
    def test(self, value):
        return hasattr(value, "__sub__")

    def parse(self, value):
        return value


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
        return isinstance(value, bool)

    def parse(self, value):
        return ensure_boolean(value)
