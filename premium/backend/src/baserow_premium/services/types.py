from typing import NotRequired, TypedDict


class ServiceAggregationSeriesDict(TypedDict):
    id: int | None
    field_id: int | None
    aggregation_type: str


class ServiceAggregationGroupByDict(TypedDict):
    field_id: int | None
    mode: NotRequired[str]


class ServiceAggregationSortByDict(TypedDict):
    sort_on: str
    reference: str
    direction: str
