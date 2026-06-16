from baserow.ws.registries import PresenceFocusType


class CellFocusType(PresenceFocusType):
    type = "cell"

    def validate(self, raw_focus: dict) -> dict:
        row_id = raw_focus.get("row_id")
        field_id = raw_focus.get("field_id")
        if not isinstance(row_id, int) or not isinstance(field_id, int):
            raise ValueError("cell focus requires int row_id and field_id")
        editing = bool(raw_focus.get("editing", False))
        return {
            "type": "cell",
            "row_id": row_id,
            "field_id": field_id,
            "editing": editing,
        }


class RowFocusType(PresenceFocusType):
    type = "row"

    def validate(self, raw_focus: dict) -> dict:
        row_id = raw_focus.get("row_id")
        if not isinstance(row_id, int):
            raise ValueError("row focus requires int row_id")
        editing = bool(raw_focus.get("editing", False))
        return {"type": "row", "row_id": row_id, "editing": editing}
