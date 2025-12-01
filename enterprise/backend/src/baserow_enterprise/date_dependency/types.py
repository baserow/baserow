from datetime import timedelta
from typing import Optional, TypedDict


class DateDepenencyDict(TypedDict):
    start_date_field_id: int
    end_date_field_id: int
    duration_field_id: int

    dependency_linkrow_field_id: Optional[int]
    dependency_linkrow_role: Optional[str]
    dependency_connection_type: Optional[str]
    dependency_buffer_type: Optional[str]
    dependency_buffer: Optional[timedelta | int]

    include_weekends: bool
