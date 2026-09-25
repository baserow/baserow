import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from django.db import connection, models

from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.types import (
    BASEROW_FORMULA_FORMAT_PLAIN,
    BASEROW_FORMULA_MODE_SIMPLE,
    BaserowFormulaFormat,
    BaserowFormulaMinified,
    BaserowFormulaMode,
    FormulaFieldDatabaseValue,
    JSONFormulaFieldDatabaseValue,
    JSONFormulaFieldResult,
)

logger = logging.getLogger(__name__)


BASEROW_FORMULA_VERSION_INITIAL = "0.1"


def _minify(
    formula: str,
    mode: BaserowFormulaMode,
    version: str,
    format: Optional[BaserowFormulaFormat] = None,
) -> BaserowFormulaMinified:
    """
    Builds the stored form of a formula object. The `fmt` key is only written
    for a format other than plain: a stored formula without `fmt` is plain, and
    `fmt: "plain"` is never written.

    :param formula: The formula string.
    :param mode: The formula mode.
    :param version: The formula version.
    :param format: The `format` of the formula object, if any.
    :return: The minified formula.
    """

    minified = BaserowFormulaMinified(m=mode, v=version, f=formula)
    if format and format != BASEROW_FORMULA_FORMAT_PLAIN:
        minified["fmt"] = format
    return minified


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
        - It can also carry the `format` of the formula object as `fmt`, e.g.
          `"fmt": "markdown"`. The key is absent when the format is plain.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For compat reasons, applied the parameters we used to receive.
        # These can be altered once we inherit from `JSONField`.
        self.default = ""
        self.null = True
        self.blank = True

    def _deserialize_baserow_object(
        self, value: FormulaFieldDatabaseValue
    ) -> Optional[Dict[str, Any]]:
        """
        Given a value from the database, attempts to deserialize it into a dictionary
        representing a Baserow formula object. If the value is not a valid JSON string
        representing a Baserow formula object, returns None.

        :param value: The value from the database to deserialize.
        :return: A dictionary representing the Baserow formula object, or None if
            deserialization fails.
        """

        if not isinstance(value, str):
            return None

        if not (value.startswith("{") and value.endswith("}")):
            return None

        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None

    def _minified_to_object(
        self, minified: BaserowFormulaMinified
    ) -> BaserowFormulaObject:
        """
        Expands a stored formula context into a `BaserowFormulaObject`, carrying
        its `fmt` over as `format` when it has one. A null `f` is read as an
        empty formula, since clients expect the formula to always be a string.

        :param minified: The stored formula context.
        :return: A `BaserowFormulaObject`.
        """

        return BaserowFormulaObject.create(
            # Raw DB values can hold `"f": null`; clients expect a string.
            formula=minified["f"] or "",
            mode=minified["m"],
            version=minified["v"],
            format=minified.get("fmt"),
        )

    def _legacy_text_to_object(self, value: str) -> BaserowFormulaObject:
        """
        Wraps a stored plain string, one that isn't a serialized formula context,
        in a simple-mode `BaserowFormulaObject`: it is a legacy formula string.

        :param value: The stored string.
        :return: A `BaserowFormulaObject`.
        """

        return BaserowFormulaObject(
            formula=value,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
            version=BASEROW_FORMULA_VERSION_INITIAL,
        )

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
            if value is None:
                return BaserowFormulaObject.create("")

            if isinstance(value, int):
                # A small hack for our backend tests: if we
                # receive an integer, we convert it to a string.
                value = str(value)
            # We could encounter a serialized object...
            if context := self._deserialize_baserow_object(value):
                # If we have, then we can parse it and return the `BaserowFormulaObject`
                return self._minified_to_object(context)
            elif isinstance(value, str):
                # Otherwise, it's a raw formula string, which we can wrap in a
                # `BaserowFormulaObject` and return.
                return self._legacy_text_to_object(value)
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
                return self._legacy_text_to_object(value)

            return self._minified_to_object(value)

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
                _minify(
                    formula="",
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                )
            )

        # v2/v2.1: if we've received a dictionary...
        if isinstance(value, dict):
            # Ensure we have proper defaults for None values. The `format` is
            # only stored (as `fmt`) when it isn't plain, see `_minify`.
            minified = _minify(
                formula=value.get("formula") or "",
                mode=value.get("mode") or BASEROW_FORMULA_MODE_SIMPLE,
                version=value.get("version") or BASEROW_FORMULA_VERSION_INITIAL,
                format=value.get("format"),
            )

            # v2: the column type is `text`, so we need to
            # serialize the object and store it in our text field.
            if self.db_type(connection) == "text":
                return json.dumps(minified)
            # v2.1: the column type is `json`, so we can store a dict.
            return minified

        # In v1.x the frontend will keep sending a formula string,
        # so we need to convert it to the new format.
        return json.dumps(
            _minify(
                formula=str(value),
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            )
        )


class JSONFormulaField(models.JSONField):
    def __init__(self, *args, **kwargs):
        self.properties = kwargs.pop("properties", [])
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        """
        Deconstruct as a regular JSONField to avoid migration detection, this
        class should be a drop-in replacement for JSONField.
        """

        name, path, args, kwargs = super().deconstruct()
        path = "django.db.models.JSONField"
        return name, path, args, kwargs

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
            # Get the intended formula field value...
            value = getattr(instance, field_name, None)
            # Process it with `to_python` to ensure it's in the correct format.
            setattr(instance, field_name, field_instance.to_python(value))
            return result

        cls.save = save_with_to_python

    def _transform_db_property(
        self,
        value: Union[str, BaserowFormulaMinified, BaserowFormulaObject],
    ) -> BaserowFormulaObject:
        """
        Responsible for taking a `value` from our database, which will be a string or
        `BaserowFormulaMinified`, and transforming it into a `BaserowFormulaObject`.

        - We will receive a formula string if we've got a legacy `JSONField` which
          hasn't yet been migrated to an object.
        - We will receive a `BaserowFormulaMinified` if we've got a migrated object
          which we've persisted to the database.
        - We will receive a `BaserowFormulaObject` if we're being called via
          `to_python`.

        Either object form can carry a format (`fmt` when minified, `format`
        otherwise), which is only kept on the result when it isn't plain.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaObject`.
        """

        # Legacy rows written before the formula-object migration can hold
        # `null` at a formula path, and older write paths could persist a null
        # `f`; clients expect `formula` to always be a string, so coerce it
        # while reading. Only the formula is coerced on purpose: a missing mode
        # or version is not guessed here.
        if not isinstance(value, dict):
            return BaserowFormulaObject(
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
                formula=value or "",
            )
        return BaserowFormulaObject.create(
            mode=value.get("m", value.get("mode")),
            version=value.get("v", value.get("version")),
            formula=value.get("f", value.get("formula")) or "",
            format=value.get("fmt", value.get("format")),
        )

    def _transform_db_properties(
        self, value: JSONFormulaFieldDatabaseValue
    ) -> JSONFormulaFieldResult:
        """
        Responsible for taking a `value` from our database, which could be a
        string, dictionary, or list of dictionaries, and transforming it into a
        `JSONFormulaFieldResult` (either a `BaserowFormulaObject` or list
        of dictionaries containing `BaserowFormulaObject`s) at their designated paths.

        :param value: The value from the database.
        :return: A `JSONFormulaFieldResult`.
        """

        # Iterate over the properties bound to this field.
        # Each property represents a path to a formula field
        # we need to convert from minified to full.
        for path in self.properties:
            # A path can be nested, e.g. "parent.child",
            # or just a single level, e.g. "parent".
            parent_path, child_path = (
                path.split(".", 1) if "." in path else (path, None)
            )
            # If `value` is a dictionary, we'll extract the nested value from it.
            # However, if it's a list, then the `value` itself is our property value.
            property_value = (
                value.get(parent_path) if isinstance(value, dict) else value
            )

            # Sometimes in tests we don't set all formula properties correctly.
            if property_value is None:
                continue

            # If we have a list of values to work with...
            if isinstance(property_value, list):
                # Iterate over each item in this list, transforming the
                # relevant property to a `BaserowFormulaObject`.
                object_list_value = []
                for item in property_value:
                    # If there's no `child_path` (i.e. it's just "parent"),
                    # then we transform the `item[parent_path]` value. E.g.
                    # [{parent: "formula"}] > [{parent: BaserowFormulaObject}]
                    if child_path is None:
                        object_value = self._transform_db_property(item[parent_path])
                        object_list_value.append(item | {parent_path: object_value})
                    else:
                        # However if we have a `child_path` (i.e. it's "parent.child"),
                        # then we transform the `item[child_path]` value. E.g.
                        # [{parent: {child: "'formula'"}}] >
                        #   [{parent: {child: BaserowFormulaObject}}]
                        object_value = self._transform_db_property(item[child_path])
                        # Rebuild the item with the transformed value, making sure
                        # we preserve any other keys in the item.
                        object_list_value.append(item | {child_path: object_value})

                # If we have a `child_path`, then we set the transformed list
                # on `value[parent_path]`. Otherwise, we set the entire `value
                # to be the transformed list.
                if child_path:
                    value[parent_path] = object_list_value
                else:
                    value = object_list_value
            else:
                # Otherwise, we have a dictionary, so we transform the
                # `property_value` directly.
                object_value = self._transform_db_property(property_value)
                value[path] = object_value

        return value

    def to_python(self, value: JSONFormulaFieldDatabaseValue) -> JSONFormulaFieldResult:
        """
        Called during create/update and deserialization. We will call
        `_transform_db_properties` to ensure we always return a
        `JSONFormulaFieldResult`.

        :param value: The value from the database, either a string or dictionary.
        :return: A `JSONFormulaFieldResult` nested inside a dictionary.
        """

        value = super().to_python(value)
        return self._transform_db_properties(value)

    def from_db_value(
        self, value: JSONFormulaFieldDatabaseValue, *args
    ) -> JSONFormulaFieldResult:
        """
        Called when reading from the database. We will call
        `_transform_db_properties` to ensure we always return a
        `JSONFormulaFieldResult` nested inside a dictionary.

        :param value: The value from the database, either a string or dictionary.
        :return: A `JSONFormulaFieldResult` nested inside a dictionary.
        """

        value = super().from_db_value(value, *args)
        return self._transform_db_properties(value)

    def _transform_python_property(
        self, value: Union[str, BaserowFormulaObject]
    ) -> BaserowFormulaMinified:
        """
        Responsible for taking a `value`, which could be a string
        or dictionary, and transforming it into a `BaserowFormulaMinified`
        for `get_prep_value` to persist in our database. The `format` of the
        object is stored as `fmt`, and only when it isn't plain.

        :param value: The value from the database, either a string or dictionary.
        :return: A `BaserowFormulaMinified`.
        """

        # Coerce `None` values so that non-serializer write paths (direct ORM
        # saves, application import) can never persist a null formula.
        if not isinstance(value, dict):
            return _minify(
                formula=value or "",
                mode=BASEROW_FORMULA_MODE_SIMPLE,
                version=BASEROW_FORMULA_VERSION_INITIAL,
            )
        return _minify(
            formula=value.get("formula") or "",
            mode=value.get("mode", BASEROW_FORMULA_MODE_SIMPLE),
            version=value.get("version", BASEROW_FORMULA_VERSION_INITIAL),
            format=value.get("format"),
        )

    def get_prep_value(
        self, value: Union[BaserowFormulaObject, List[Dict[str, BaserowFormulaObject]]]
    ) -> JSONFormulaFieldDatabaseValue:
        """
        Responsible for converting a Python value to database value. Our Python
        value could be a dictionary (a `BaserowFormulaObject`), or a list
        of dictionaries (a list of `BaserowFormulaObject`s). We need to convert
        both of these into a `BaserowFormulaMinified` object, or a list of
        `BaserowFormulaMinified` objects at their designated paths.

        :param value: The value to convert, either a string or `BaserowFormulaObject`.
        :return: A `JSONFormulaFieldDatabaseValue`.
        """

        # If we receive an empty dict or string, just return early.
        # We'll be back in a moment with a value (e.g. creating a
        # record with no json value, then updating it).
        if not value:
            return value

        # We only process dictionaries and lists.
        # If we receive anything else (e.g. via a receiver such as
        # `page_deleted_update_link_collection_fields`), then return its value.
        if not isinstance(value, (dict, list)):
            return value

        # Work on a copy: the minification below mutates `value` in place, but
        # `value` is the model instance's in-memory attribute. Mutating it as a
        # side effect of preparing the DB value is unsafe when `get_prep_value`
        # runs more than once for a single save (e.g. django-silk compiles each
        # query twice for logging) — the second run would re-minify the
        # already-minified value and blank the formula. Copying keeps the
        # in-memory value untouched (full form) so re-runs are idempotent.
        value = deepcopy(value)

        # Iterate over the properties bound to this field.
        # Each property represents a path to a formula field
        # we need to convert from full to minified.
        for path in self.properties:
            # A path can be nested, e.g. "parent.child",
            # or just a single level, e.g. "parent".
            parent_path, child_path = (
                path.split(".", 1) if "." in path else (path, None)
            )
            # If `value` is a dictionary, we'll extract the nested value from it.
            # However, if it's a list, then the `value` itself is our property value.
            property_value: Union[BaserowFormulaObject, List] = (
                value.get(parent_path) if isinstance(value, dict) else value
            )

            # Sometimes in tests we don't set all formula properties correctly.
            if property_value is None:
                continue

            # If we have a list of values to work with...
            if isinstance(property_value, list):
                # Iterate over each item in this list, transforming the
                # relevant property to a `BaserowFormulaMinified`.
                minified_list_value = []
                for item in property_value:
                    # If there's no `child_path` (i.e. it's just "parent"),
                    # then we transform the `item[parent_path]` value. E.g.
                    # [{parent: BaserowFormulaObject}] ->
                    #   [{parent: BaserowFormulaMinified}]
                    if child_path is None:
                        minified_value = self._transform_python_property(
                            item[parent_path]
                        )
                        minified_list_value.append(item | {parent_path: minified_value})
                    else:
                        # However if we have a `child_path` (i.e. it's "parent.child"),
                        # then we transform the `item[child_path]` value. E.g.
                        # [{parent: {child: BaserowFormulaObject}}] ->
                        #   [{parent: {child: BaserowFormulaMinified}}]
                        minified_value = self._transform_python_property(
                            item[child_path]
                        )
                        minified_list_value.append(item | {child_path: minified_value})

                # If we have a `child_path`, then we set the transformed list
                # on `value[parent_path]`. Otherwise, we set the entire `value
                # to be the transformed list.
                if child_path:
                    value[parent_path] = minified_list_value
                else:
                    value = minified_list_value
            else:
                # Otherwise, we have a dictionary, so we transform the
                # `property_value` directly.
                minified_value = self._transform_python_property(property_value)
                value[path] = minified_value

        return value
