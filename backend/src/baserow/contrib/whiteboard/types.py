from typing import Any, TypedDict


class WhiteboardDict(TypedDict):
    id: int
    name: str
    content: dict[str, Any]
    order: str
    type: str
