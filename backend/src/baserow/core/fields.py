import decimal
import math
from functools import cached_property

from django import forms
from django.core import checks, exceptions, validators
from django.db import models
from django.db.models.fields.related_descriptors import ReverseOneToOneDescriptor
from django.db.transaction import atomic
from django.utils.translation import gettext_lazy as _


class SyncedDateTimeField(models.DateTimeField):
    def __init__(self, sync_with=None, sync_with_add=None, *args, **kwargs):
        self.sync_with = sync_with
        self.sync_with_add = sync_with_add
        if sync_with or sync_with_add:
            kwargs["editable"] = False
            kwargs["blank"] = True
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        if add and self.sync_with_add:
            value = getattr(model_instance, self.sync_with_add)
            setattr(model_instance, self.attname, value)
            return value
        elif self.sync_with:
            value = getattr(model_instance, self.sync_with)
            setattr(model_instance, self.attname, value)
            return value
        else:
            return super().pre_save(model_instance, add)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.sync_with or self.sync_with_add:
            kwargs.pop("editable", None)
            kwargs.pop("blank", None)
        return name, path, args, kwargs


class AutoTrueBooleanField(models.BooleanField):
    """
    A `BooleanField` which automatically sets itself to `True` before a save takes
    place. Used by `ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME` to mark a row as
    needing a background update after it's been created or updated.
    """

    def pre_save(self, model_instance, add):
        setattr(model_instance, self.attname, True)
        return super().pre_save(model_instance, add)


class AutoSingleRelatedObjectDescriptor(ReverseOneToOneDescriptor):
    """
    The descriptor that handles the object creation for an AutoOneToOneField.

    This class is inspired by:
    https://github.com/skorokithakis/django-annoying/blob/master/annoying/fields.py
    """

    def __get__(self, instance, instance_type=None):
        model = getattr(self.related, "related_model", self.related.model)

        try:
            return super(AutoSingleRelatedObjectDescriptor, self).__get__(
                instance, instance_type
            )
        except model.DoesNotExist:
            with atomic():
                # Using get_or_create instead() of save() or create() as it better
                # handles race conditions
                obj, _ = model.objects.get_or_create(
                    **{self.related.field.name: instance}
                )

                # Update Django's cache, otherwise first 2 calls to obj.relobj
                # will return 2 different in-memory objects
                self.related.set_cached_value(instance, obj)
                self.related.field.set_cached_value(obj, instance)
                return obj


class AutoOneToOneField(models.OneToOneField):
    """
    OneToOneField creates related object on first call if it doesn't exist yet.
    Use it instead of original OneToOne field.

    example:

        class MyProfile(models.Model):
            user = AutoOneToOneField(User, primary_key=True)
            home_page = models.URLField(max_length=255, blank=True)
            icq = models.IntegerField(max_length=255, null=True)
    """

    def contribute_to_related_class(self, cls, related):
        setattr(
            cls, related.get_accessor_name(), AutoSingleRelatedObjectDescriptor(related)
        )


class LenientDecimalField(models.Field):
    """
    Copy of Django 4.1.X DecimalField that allows NaN values

    This is needed for instance in the formula language that uses NaN
    to store invalid number results for formulas like 1/field('a')
    where field('a') can be zero.
    """

    empty_strings_allowed = False
    default_error_messages = {
        "invalid": _("“%(value)s” value must be a decimal number."),
    }
    description = _("Decimal number")

    def __init__(
        self,
        verbose_name=None,
        name=None,
        max_digits=None,
        decimal_places=None,
        **kwargs,
    ):
        self.max_digits, self.decimal_places = max_digits, decimal_places
        super().__init__(verbose_name, name, **kwargs)

    def check(self, **kwargs):
        errors = super().check(**kwargs)

        digits_errors = [
            *self._check_decimal_places(),
            *self._check_max_digits(),
        ]
        if not digits_errors:
            errors.extend(self._check_decimal_places_and_max_digits(**kwargs))
        else:
            errors.extend(digits_errors)
        return errors

    def _check_decimal_places(self):
        try:
            decimal_places = int(self.decimal_places)
            if decimal_places < 0:
                raise ValueError()
        except TypeError:
            return [
                checks.Error(
                    "DecimalFields must define a 'decimal_places' attribute.",
                    obj=self,
                    id="fields.E130",
                )
            ]
        except ValueError:
            return [
                checks.Error(
                    "'decimal_places' must be a non-negative integer.",
                    obj=self,
                    id="fields.E131",
                )
            ]
        else:
            return []

    def _check_max_digits(self):
        try:
            max_digits = int(self.max_digits)
            if max_digits <= 0:
                raise ValueError()
        except TypeError:
            return [
                checks.Error(
                    "DecimalFields must define a 'max_digits' attribute.",
                    obj=self,
                    id="fields.E132",
                )
            ]
        except ValueError:
            return [
                checks.Error(
                    "'max_digits' must be a positive integer.",
                    obj=self,
                    id="fields.E133",
                )
            ]
        else:
            return []

    def _check_decimal_places_and_max_digits(self, **kwargs):
        if int(self.decimal_places) > int(self.max_digits):
            return [
                checks.Error(
                    "'max_digits' must be greater or equal to 'decimal_places'.",
                    obj=self,
                    id="fields.E134",
                )
            ]
        return []

    @cached_property
    def validators(self):
        return super().validators + [
            validators.DecimalValidator(self.max_digits, self.decimal_places)
        ]

    @cached_property
    def context(self):
        return decimal.Context(prec=self.max_digits)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.max_digits is not None:
            kwargs["max_digits"] = self.max_digits
        if self.decimal_places is not None:
            kwargs["decimal_places"] = self.decimal_places
        return name, path, args, kwargs

    def get_internal_type(self):
        return "DecimalField"

    def to_python(self, value):
        if value is None:
            return value
        if isinstance(value, float):
            if math.isnan(value):
                raise exceptions.ValidationError(
                    self.error_messages["invalid"],
                    code="invalid",
                    params={"value": value},
                )
            return self.context.create_decimal_from_float(value)
        try:
            return decimal.Decimal(value)
        except (decimal.InvalidOperation, TypeError, ValueError):
            raise exceptions.ValidationError(
                self.error_messages["invalid"],
                code="invalid",
                params={"value": value},
            )

    def get_db_prep_save(self, value, connection):
        return connection.ops.adapt_decimalfield_value(
            self.to_python(value), self.max_digits, self.decimal_places
        )

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return self.to_python(value)

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "max_digits": self.max_digits,
                "decimal_places": self.decimal_places,
                "form_class": forms.DecimalField,
                **kwargs,
            }
        )


def default_boolean_list(num_flags):
    """Returns a default list of False values"""

    return [False] * num_flags


class MultipleFlagField(models.CharField):
    """Stores a list of booleans as a binary string"""

    def __init__(self, num_flags=8, default=None, *args, **kwargs):
        self.num_flags = num_flags
        kwargs.setdefault("max_length", num_flags)  # Ensures max length is set

        # Handle list-based default values properly
        if default is None:
            default = default_boolean_list(num_flags)
        if isinstance(default, list):
            if len(default) != num_flags:
                raise ValueError(f"Default list must have exactly {num_flags} elements")
            # Convert list to string representation
            kwargs["default"] = "".join("1" if flag else "0" for flag in default)
        elif isinstance(default, str):
            if len(default) != num_flags or not set(default).issubset({"0", "1"}):
                raise ValueError(
                    f"Default string must be exactly {num_flags} characters of "
                    "'0' or '1'"
                )
            kwargs["default"] = default
        else:
            raise ValueError(
                "Default must be a list of booleans, a binary string, or None"
            )

        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        """
        Converts the stored binary string into a list of booleans when retrieving
        from the database
        """

        if value is None:
            return default_boolean_list(self.num_flags)
        return [char == "1" for char in value]

    def to_python(self, value):
        """Ensures the value is always returned as a list of booleans"""

        if isinstance(value, list):
            return value
        return [char == "1" for char in value]

    def get_prep_value(self, value):
        """Converts the list of booleans into a binary string for database storage"""

        if isinstance(value, str):
            # If Django passes the default value as a string, assume it's already in
            # correct format
            if len(value) != self.num_flags or not set(value).issubset({"0", "1"}):
                raise ValueError(
                    f"Stored string must have exactly {self.num_flags} characters of "
                    "'0' or '1'"
                )
            return value
        elif isinstance(value, list):
            if len(value) != self.num_flags:
                raise ValueError(f"List must have exactly {self.num_flags} elements")
            return "".join("1" if flag else "0" for flag in value)
        else:
            raise ValueError(
                "Value must be a list of booleans or a valid binary string"
            )

    def deconstruct(self):
        """Ensures Django migrations correctly store and restore num_flags"""

        name, path, args, kwargs = super().deconstruct()
        kwargs["num_flags"] = self.num_flags  # Add num_flags explicitly
        return name, path, args, kwargs
