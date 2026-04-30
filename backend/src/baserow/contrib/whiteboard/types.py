from typing import Any, TypedDict


class WhiteboardDict(TypedDict):
    id: int
    name: str
    order: str
    type: str
    content: dict[str, Any]
