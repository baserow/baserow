from typing import Any, Dict, List, Optional

import advocate
from advocate.exceptions import UnacceptableAddressException
from icalendar import Calendar
from requests.exceptions import RequestException

from baserow.contrib.database.fields.models import DateField, TextField
from baserow.core.utils import ChildProgressBuilder

from .exceptions import SyncError
from .models import ICalCalendarDataSync
from .registries import DataSyncProperty, DataSyncType
from .utils import compare_date


class UIDICalCalendarDataSyncProperty(DataSyncProperty):
    unique_primary = True
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class DateStartICalCalendarDataSyncProperty(DataSyncProperty):
    immutable_properties = False

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
        )

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)


class DateEndICalCalendarDataSyncProperty(DataSyncProperty):
    immutable_properties = False

    def to_baserow_field(self) -> DateField:
        return DateField(
            name=self.name,
            date_format="ISO",
            date_include_time=True,
            date_time_format="24",
            date_show_tzinfo=True,
        )

    def is_equal(self, baserow_row_value: Any, data_sync_row_value: Any) -> bool:
        return compare_date(baserow_row_value, data_sync_row_value)


class SummaryICalCalendarDataSyncProperty(DataSyncProperty):
    immutable_properties = True

    def to_baserow_field(self) -> TextField:
        return TextField(name=self.name)


class ICalCalendarDataSyncType(DataSyncType):
    type = "ical_calendar"
    model_class = ICalCalendarDataSync
    allowed_fields = ["ical_url"]
    serializer_field_names = ["ical_url"]
    request_serializer_field_names = ["ical_url"]

    def get_properties(self, instance) -> List[DataSyncProperty]:
        return [
            UIDICalCalendarDataSyncProperty("uid", "Unique ID"),
            DateStartICalCalendarDataSyncProperty("dtstart", "Start date"),
            DateEndICalCalendarDataSyncProperty("dtend", "End date"),
            SummaryICalCalendarDataSyncProperty("summary", "Summary"),
        ]

    def get_all_rows(
        self,
        instance,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict]:
        # The progress bar is difficult to setup because there are only three steps
        # that must completed. We're therefore using working with a total of three
        # because it gives some sense of what's going on.
        progress = ChildProgressBuilder.build(progress_builder, child_total=3)

        try:
            response = advocate.get(instance.ical_url, timeout=60)
        except (RequestException, UnacceptableAddressException, ConnectionError):
            raise SyncError("The provided URL could not be reached.")

        if not response.ok:
            raise SyncError(
                "The request to the URL didn't respond with an OK response code."
            )
        progress.increment(by=1)  # makes the total `1`

        try:
            calendar = Calendar.from_ical(response.content)
        except ValueError as e:
            raise SyncError(f"Could not read calendar file: {str(e)}")
        progress.increment(by=1)  # makes the total `2`

        events = [
            {
                "uid": str(component.get("uid")),
                "dtstart": getattr(component.get("dtstart"), "dt", None),
                "dtend": getattr(component.get("dtend"), "dt", None),
                "summary": str(component.get("summary") or ""),
            }
            for component in calendar.walk()
            if component.name == "VEVENT"
        ]
        progress.increment(by=1)  # makes the total `3`

        return events
