from baserow.ws.registries import PresenceFocusType


def _validate_int_id(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    return value


def _validate_editing(raw_focus: dict) -> bool:
    editing = raw_focus.get("editing", False)
    return editing if isinstance(editing, bool) else False


class CellFocusType(PresenceFocusType):
    type = "cell"

    def validate(self, raw_focus: dict) -> dict:
        row_id = _validate_int_id(raw_focus.get("row_id"), "row_id")
        field_id = _validate_int_id(raw_focus.get("field_id"), "field_id")
        return {
            "type": "cell",
            "row_id": row_id,
            "field_id": field_id,
            "editing": _validate_editing(raw_focus),
        }


class RowFocusType(PresenceFocusType):
    type = "row"

    def validate(self, raw_focus: dict) -> dict:
        row_id = _validate_int_id(raw_focus.get("row_id"), "row_id")
        return {
            "type": "row",
            "row_id": row_id,
            "editing": _validate_editing(raw_focus),
        }
