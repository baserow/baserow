from typing import TypedDict


class ServiceAggregationSeriesDict(TypedDict):
    field_id: int
    aggregation_type: str


class ServiceAggregationGroupByDict(TypedDict):
    field_id: int


class ServiceAggregationSortByDict(TypedDict):
    sort_on: str
    reference: str
    direction: str
