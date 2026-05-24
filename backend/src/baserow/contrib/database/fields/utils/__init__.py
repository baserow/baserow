import re
from typing import Optional, Union

from .deferred_field_importer import DeferredFieldImporter  # noqa: F401
from .deferred_foreign_key_updater import DeferredForeignKeyUpdater  # noqa: F401
from .schema import guess_json_type_from_response_serializer_field  # noqa: F401

field_pattern = re.compile("^field_([0-9]+)$")


def get_field_id_from_field_key(
    value: Union[str, int], strict: bool = True
) -> Optional[int]:
    """
    Extracts the numeric value from a string that looks like `field_1`.

    :param value: The string that contains the field ID.
    :param strict: If `true`, then the value must be a number or match the `field_3`
        pattern. If false, then it tries to extract any number from the value.
    :return: The extracted field id.
    """

    if isinstance(value, int):
        return value

    if strict and not (value.isdigit() or field_pattern.match(value)):
        return None

    try:
        return int(re.sub("[^0-9]", "", value))
    except ValueError:
        return None
