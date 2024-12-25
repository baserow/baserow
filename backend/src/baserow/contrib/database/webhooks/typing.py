from typing import List, TypedDict


class EventConfigItem(TypedDict):
    event_type: str
    fields: List[int]
