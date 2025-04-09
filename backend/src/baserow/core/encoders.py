import dataclasses
import json
from datetime import date, datetime, timedelta
from decimal import Decimal


def get_json_decoder_supporting_data_classes(data_class, many=False):
    """
    This function can be used to generate a decoder for the django ORM that can turn a
    JSONB field into a data class.

    This does currently only support a flat data class structure (no nesting).

    :param data_class: The data class that the JSONB field should be encoded to
    :param many: True if the field is an array and not a single object
    :return: The decoder class supported by django ORM
    """

    class JSONDecoderSupportingDataClasses(json.JSONDecoder):
        def decode(self, s: str):
            o = super().decode(s)

            if many:
                return [data_class(**item) for item in o]

            return data_class(**o)

    return JSONDecoderSupportingDataClasses


class JSONEncoderSupportingDataClasses(json.JSONEncoder):
    """
    This class can be used to encode data classes and be used for djangos JSONB field
    type.

    This does currently only support a flat data class structure (no nesting).
    """

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, (Decimal, datetime, date)):
            return str(o)
        elif isinstance(o, timedelta):
            return o.total_seconds()
        return super().default(o)
