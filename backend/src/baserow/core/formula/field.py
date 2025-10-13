import json
import logging
from typing import Dict, Union

from django.db import connection, models

from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.types import (
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaMinified,
    FormulaFieldDatabaseValue,
)

logger = logging.getLogger(__name__)


BASEROW_FORMULA_VERSION_INITIAL = "0.1"


class FormulaField(models.TextField):
    """
    A formula field which can contain:

    - A JSON-serialized formula string:
        - E.g. 'get(\"data_source.123.field_123\")'
        - This can happen if a user fetches a row with one or more formula fields
          which were not yet migrated to the new formula context format.
    - A JSON-serialized formula context:
        - E.g. {"f":"get(\"data_source.123.field_123\")\","m": "simple","v":"0.1"}
        - This is the new format which contains the formula string, the mode (simple,
            advanced, raw) and the version of the formula context.
    """

    def _value_is_serialized_object(self, value: FormulaFieldDatabaseValue) -> bool:
        return isinstance(value, str) and value[:1] == "{" and value[-1:] == "}"

    def _transform_db_value_to_dict(
        self, value: FormulaFieldDatabaseValue
    ) -> BaserowFormulaObject:
        """
        Responsible for taking a `value` from our database, which could be a string
        or dictionary, and transforming it into a `BaserowFormulaObject`.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaObject`.
        """

        # If the column type is "text", then we haven't yet migrated the schema.
        if self.db_type(connection) == "text":
            if isinstance(value, int):
                # A small hack for our backend tests: if we
                # receive an integer, we convert it to a string.
                value = str(value)
            # We could encounter a serialized object...
            if self._value_is_serialized_object(value):
                # If we have, then we can parse it and return the `BaserowFormulaObject`
                context = json.loads(value)
                return BaserowFormulaObject(
                    mode=context["m"], version=context["v"], formula=context["f"]
                )
            elif isinstance(value, str):
                # Otherwise, it's a raw formula string, which we can wrap in a
                # `BaserowFormulaObject` and return.
                return BaserowFormulaObject(
                    formula=value,
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                )
            # It's a dictionary, so we can assume it's already a formula context.
            # We just wrap it in a `BaserowFormulaObject` for typing purposes.
            return BaserowFormulaObject(**value)
        else:
            # We either have a serialized formula context, or a raw formula string.
            # Either way, we need to load it as JSON as the `FormulaField` does not
            # yet inherit from `JSONField`.
            try:
                value = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                logger.error(
                    "FormulaField was unable to deserialize "
                    f"value '{value}' when the column type was `json`.",
                    exc_info=True,
                )
                return BaserowFormulaObject(
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                    formula="",
                )

            if isinstance(value, str):
                return BaserowFormulaObject(
                    formula=value,
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                )

            return BaserowFormulaObject(
                mode=value["m"], version=value["v"], formula=value["f"]
            )

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

    def to_python(self, value: FormulaFieldDatabaseValue) -> BaserowFormulaObject:
        """
        Called during create/update and deserialization. We will call
        `_transform_db_value_to_dict` to ensure we always return a
        `BaserowFormulaObject`.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaObject`.
        """

        return self._transform_db_value_to_dict(value)

    def from_db_value(
        self, value: FormulaFieldDatabaseValue, *args
    ) -> BaserowFormulaObject:
        """
        Called when reading from the database. We will call
        `_transform_db_value_to_dict` to ensure we always return a
        `BaserowFormulaObject`.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaObject`.
        """

        return self._transform_db_value_to_dict(value)

    def get_prep_value(
        self, value: Union[str, BaserowFormulaObject]
    ) -> Union[str, BaserowFormulaMinified]:
        """
        Responsible for converting a Python value to database value. Our Python
        value could be a string (a raw formula string), or a `BaserowFormulaObject`.
        We need to convert both of these into a `BaserowFormulaMinified` object
        (or its JSON-serialized string representation, depending on the column type).

        :param value: The value to convert, either a string or `BaserowFormulaObject`.
        :return: Either a JSON-serialized string (if the column type is `text`)
            or a `BaserowFormulaMinified` object (if the column type is `json`).
        """

        # Mainly for defensive programming purposes: if we
        # receive `None`, we return a default empty formula context.
        # We should always be receiving a string or dictionary here.
        if value is None:
            return json.dumps(
                BaserowFormulaMinified(
                    m=BASEROW_FORMULA_MODE_SIMPLE,
                    v=BASEROW_FORMULA_VERSION_INITIAL,
                    f="",
                )
            )

        # v2/v2.1: if we've received a dictionary...
        if isinstance(value, dict):
            # Ensure we have proper defaults for None values
            mode = value.get("mode") or BASEROW_FORMULA_MODE_SIMPLE
            version = value.get("version") or BASEROW_FORMULA_VERSION_INITIAL
            formula = value.get("formula") or ""

            # v2: the column type is `text`, so we need to
            # serialize the object and store it in our text field.
            if self.db_type(connection) == "text":
                return json.dumps(BaserowFormulaMinified(m=mode, v=version, f=formula))
            # v2.1: the column type is `json`, so we can store a dict.
            return BaserowFormulaMinified(m=mode, v=version, f=formula)

        # In v1.x the frontend will keep sending a formula ,
        # string so we need to convert it to the new format.
        return json.dumps(
            BaserowFormulaMinified(
                f=str(value),
                m=BASEROW_FORMULA_MODE_SIMPLE,
                v=BASEROW_FORMULA_VERSION_INITIAL,
            )
        )


class JSONFormulaField(models.JSONField):
    def __init__(self, *args, **kwargs):
        self.property_name = kwargs.pop("property_name", None)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """
        Deconstruct as a regular JSONField to avoid migration detection, this
        class should be a drop-in replacement for JSONField.
        """

        name, path, args, kwargs = super().deconstruct()
        path = "django.db.models.JSONField"
        return name, path, args, kwargs

    def _transform_db_value_to_dict(
        self, value: Union[str, BaserowFormulaMinified]
    ) -> Dict[str, BaserowFormulaObject]:
        """
        Responsible for taking a `value` from our database, which could be a string
        or dictionary, and transforming it into a dictionary containing a
        `BaserowFormulaObject` nested inside `value[self.property_name]`.
        :param value: The value from the database, either a string or dictionary.
        :return: A dictionary containing a `BaserowFormulaObject` nested inside
        `value[self.property_name]`.
        """

        if isinstance(value, str):
            return {
                self.property_name: BaserowFormulaObject(
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                    formula=value,
                )
            }
        return {
            self.property_name: BaserowFormulaObject(
                mode=value["m"], version=value["v"], formula=value["f"]
            )
        }

    def to_python(
        self, value: Dict[str, FormulaFieldDatabaseValue]
    ) -> Dict[str, BaserowFormulaObject]:
        """
        Called during create/update and deserialization. We will call
        `_transform_db_value_to_dict` to ensure we always return a
        `BaserowFormulaObject`.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaObject` nested inside a dictionary.
        """

        value = super().to_python(value)
        return self._transform_db_value_to_dict(value[self.property_name])

    def from_db_value(
        self, value: Dict[str, FormulaFieldDatabaseValue], *args
    ) -> Dict[str, BaserowFormulaObject]:
        """
        Called when reading from the database. We will call
        `_transform_db_value_to_dict` to ensure we always return a
        `BaserowFormulaObject` nested inside a dictionary.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaObject` nested inside a dictionary.
        """

        value = super().from_db_value(value, *args)
        return self._transform_db_value_to_dict(value[self.property_name])

    def get_prep_value(
        self, value: Dict[str, Union[str, BaserowFormulaObject]]
    ) -> Dict[str, BaserowFormulaMinified]:
        """
        Responsible for converting a formula string, or `BaserowFormulaObject` to a
        `BaserowFormulaMinified` object, nested inside `value[self.property_name]`.
        :param value: The value to convert, either a string or `BaserowFormulaObject`.
        :return: A `BaserowFormulaMinified` object nested inside a dictionary.
        """

        formula = value.get(self.property_name, {})
        if isinstance(formula, str):
            return {
                self.property_name: BaserowFormulaMinified(
                    m=BASEROW_FORMULA_MODE_SIMPLE,
                    v=BASEROW_FORMULA_VERSION_INITIAL,
                    f=formula,
                )
            }
        return {
            self.property_name: BaserowFormulaMinified(
                m=formula.get("mode", BASEROW_FORMULA_MODE_SIMPLE),
                v=formula.get("version", BASEROW_FORMULA_VERSION_INITIAL),
                f=formula.get("formula", ""),
            )
        }
