import json
from typing import TypedDict

from django.db import models, connection

from baserow.core.formula.types import BaserowFormula


class BaserowFormulaContext(TypedDict):
    mode: str
    version: str
    formula: BaserowFormula


class FormulaField(models.TextField):
    """
    A formula field contains the text value of a runtime formula like:
    - concat("test:", get("page_parameter.id"), "-")
    - get("data_source.Product.id")

    For now it's just a text field but we can add layer of validation later.
    """

    def _value_is_serialized_object(self, value) -> bool:
        return isinstance(value, str) and value[:1] == "{" and value[-1:] == "}"

    def contribute_to_class(self, cls, name, **kwargs):
        """
        Due to a limitation of Django's ORM after saving, it keeps the original value
        in memory without re-processing it through `to_python`. We need to override the
        save method to ensure the value is transformed correctly after each save.
        """

        super().contribute_to_class(cls, name, **kwargs)

        # Store references for closure
        field_name = name
        field_instance = self
        original_save = cls.save

        def save_with_to_python(instance, *args, **kwargs):
            # Perform the original save operation
            result = original_save(instance, *args, **kwargs)
            # Get the intended formula field value, and process it
            # with `to_python` to ensure it's in the correct format.
            value = getattr(instance, field_name, None)
            setattr(instance, field_name, field_instance.to_python(value))
            return result

        cls.save = save_with_to_python

    def _transform_value_to_context(self, value):
        """Shared transformation logic."""
        if value is None:
            return None

        # If the column type is "text", then we haven't yet migrated the schema.
        if self.db_type(connection) == "text":
            # We could encounter a serialized object...
            if self._value_is_serialized_object(value):
                # If we have, then we can parse it and return the `BaserowFormulaContext`.
                context = json.loads(value)
                return BaserowFormulaContext(
                    mode=context["m"], version=context["v"], formula=context["f"]
                )
            elif isinstance(value, str):
                # Otherwise, it's a raw formula string, which we can wrap in a
                # `BaserowFormulaContext` and return.
                return BaserowFormulaContext(
                    mode="simple", version="1.0", formula=value
                )
            # It's a dictionary, so we'll assume it's a valid
            # formula context and return it as is.
            return value
        else:
            # The column has been migrated to a `jsonb` column.
            # If we receive a string now, it's always a formula string. Serialized
            # objects would be deserialized by Django automatically
            if isinstance(value, str):
                return BaserowFormulaContext(
                    mode="simple", version="1.0", formula=value
                )
            return BaserowFormulaContext(
                mode=value["m"], version=value["v"], formula=value["f"]
            )

    def to_python(self, value):
        """Called during create/update and deserialization."""
        return self._transform_value_to_context(value)

    def from_db_value(self, value, expression, connection):
        """Called when reading from database."""
        return self._transform_value_to_context(value)

    def get_prep_value(self, value):
        """Convert Python object to database value."""
        if value is None:
            return None

        # If we've been given a dictionary, we'll construct the
        # "modified" version of the formula context and persist it.
        if isinstance(value, dict):
            if self.db_type(connection) == "text":
                return json.dumps(
                    {
                        "m": value.get("mode"),
                        "v": value.get("version"),
                        "f": value.get("formula"),
                    }
                )
            # If we've already migrated to a jsonb column,
            # we can just return the value as is.
            return value
        # If the value is a serialized object, there's no
        # serialization to do, so just return it as is.
        elif self._value_is_serialized_object(value):
            return value

        # We've got a formula string - we'll construct our formula
        # context and return it as its formula value.
        return json.dumps(
            {
                "m": "simple",
                "v": "1.0",
                "f": value,
            }
        )
