import json
import re
from datetime import date, datetime
from decimal import Decimal
from json.decoder import JSONDecodeError
from typing import Any, List, Optional, Union

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from baserow.contrib.database.fields.constants import (
    BASEROW_BOOLEAN_FIELD_FALSE_VALUES,
    BASEROW_BOOLEAN_FIELD_TRUE_VALUES,
)
from baserow.core.datetime import FormattedDate, FormattedDateTime


def ensure_boolean(value: Any, strict=True) -> bool:
    """
    Ensures that the value is a boolean or converts it.

    :param value: The value to ensure as a boolean.
    :param strict: If not strict, an attempt is made to cast the value to a bool.
    :return: The value as a boolean.
    :raises ValidationError: if the value is not a valid boolean or convertible to a
        boolean.
    """

    if value in BASEROW_BOOLEAN_FIELD_TRUE_VALUES:
        return True
    elif value in BASEROW_BOOLEAN_FIELD_FALSE_VALUES:
        return False

    if not strict:
        return bool(value)

    raise ValidationError("Value is not a valid boolean or convertible to a boolean.")


def ensure_numeric(
    value: Any, allow_null: bool = False
) -> Optional[Union[int, float, Decimal]]:
    """
    Ensures that the value is a number or can be converted to a numeric value.

    :param value: The value to ensure as a number.
    :param allow_null: Whether to allow null or empty values.
    :return: The value as a number (int, float, or Decimal) if conversion is successful.
    :raises ValidationError: If the value is not a valid number or convertible
    to a number.
    """

    if allow_null and (value is None or value == ""):
        return None

    # Handle numeric types directly
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return value

    # Handle string conversion
    if isinstance(value, str):
        # Check if the string matches a valid number pattern
        if re.match(r"^([-+])?(\d+(\.\d+)?)$", value):
            # Convert to int if it's a whole number, otherwise float
            try:
                num_value = float(value)
                if num_value.is_integer():
                    return int(value)
                return num_value
            except ValueError:
                # If float conversion fails, try Decimal as a fallback
                try:
                    return Decimal(value)
                except Exception as exc:
                    raise ValidationError(
                        f"Value '{value}' is not a valid number or convertible to a number."
                    ) from exc

    raise ValidationError(
        f"Value '{value}' is not a valid number or convertible to a number."
    )


def ensure_integer(value: Any, allow_empty: bool = False) -> Optional[int]:
    """
    Ensures that the value is an integer or can be converted to an integer.
    Raises a ValidationError if the value is not a valid integer or convertible to an
    integer.

    :param value: The value to ensure as an integer.
    :param allow_empty: Whether we should throw an error if `value` is empty.
    :return: The value as an integer if conversion is successful.
    :raises ValidationError: If the value is not a valid integer or convertible to an
        integer.
    """

    if value is None or value == "":
        if not allow_empty:
            raise ValidationError("The value is required")
        return None

    try:
        return int(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "The value must be an integer or convertible to an integer."
        ) from exc


def ensure_string(value: Any, allow_empty: bool = True) -> str:
    """
    Ensures that the value is a string or try to convert it.

    :param value: The value to ensure as a string.
    :param allow_empty: Whether we should throw an error if `value` is empty.
    :return: The value as a string.
    :raises ValidationError: If not allow_empty and the `value` is empty.
    """

    if value is None or value == "" or value == [] or value == {}:
        if not allow_empty:
            raise ValidationError("A valid String is required.")
        return ""

    if isinstance(value, bool):
        # To match the frontend
        return "true" if value else "false"
    if isinstance(value, list):
        results = [ensure_string(item) for item in value if item]
        return ",".join(results)
    elif isinstance(value, dict):
        return json.dumps(value)

    return str(value)


def ensure_string_or_integer(value: Any, allow_empty: bool = True) -> Union[int, str]:
    """
    Ensures that the value is a string or an integer.

    :param value: The value to ensure as a string.
    :param allow_empty: Whether we should throw an error if `value` is empty.
    :return: The value as a string.
    :raises ValidationError: If not allow_empty and the `value` is empty.
    """

    if isinstance(value, int):
        return value

    return ensure_string(value, allow_empty=allow_empty)


def ensure_array(value: Any, allow_empty: bool = True) -> List[Any]:
    """
    Ensure that the value is an array or try to convert it.
    Strings will be treated as comma separated values.
    Other data types will be transformed into a single element array.

    :param value: The value to ensure as an array.
    :param allow_empty: Whether we should raise an error if `value` is empty.
    :return: The value as an array.
    :raises ValidationError: if not allow_empty and `value` is empty.
    """

    if value is None or value == "" or (isinstance(value, list) and not value):
        if not allow_empty:
            raise ValidationError("A non empty value is required.")
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        return [item.strip() for item in value.split(",")]

    return [value]


def ensure_email(value: Any) -> str:
    """
    Ensures that the value is an email or can be converted to an email.
    :param value: The value to ensure as an email.
    :return: The value as an email.
    :raises ValidationError: If the value is not a valid email or convertible to an
      email.
    """

    str_value = ensure_string(value)

    validate_email(str_value)

    return str_value


def ensure_date(value: Any) -> Optional[date]:
    """
    Ensures that the value is a date or can be converted to a date.
    :param value: The value to ensure as a date.
    :return: The value as a date.
    :raises ValidationError: If the value is not a valid date or convertible to a date.
    """

    try:
        return FormattedDate(value).date if value is not None else None
    except (ValueError, TypeError) as exc:
        raise ValidationError("Value cannot be converted to a date.") from exc


def ensure_datetime(value: Any) -> Optional[datetime]:
    """
    Ensures that the value is a datetime or can be converted to a datetime.
    :param value: The value to ensure as a datetime.
    :return: The value as a datetime.
    :raises ValidationError: If the value is not a valid datetime or convertible to a
        datetime.
    """

    try:
        return FormattedDateTime(value).datetime if value is not None else None
    except (ValueError, TypeError) as exc:
        raise ValidationError("Value cannot be converted to a datetime.") from exc


def ensure_object(value: Any) -> Optional[dict]:
    """
    Ensures that the value is a dict or can be converted to a dict.
    :param value: The value to ensure as a dict.
    :return: The value as a dict.
    :raises ValidationError: If the value is not a valid dict or convertible to a
        dict.
    """

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, JSONDecodeError) as exc:
            raise ValidationError("Value is not a JSON.") from exc

    raise ValidationError("Value cannot be converted to a dict.")
