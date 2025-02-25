from django.conf import settings

from baserow_premium.views.models import CalendarViewFieldOptions
from rest_framework import serializers

from baserow.contrib.database.api.rows.serializers import (
    get_example_multiple_rows_metadata_serializer,
    get_example_row_serializer_class,
)
from baserow.contrib.database.search.handler import ALL_SEARCH_MODES
from baserow.core.datetime import get_timezones


class CalendarViewFieldOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarViewFieldOptions
        fields = (
            "hidden",
            "order",
        )


class ListCalendarRowsQueryParamsSerializer(serializers.Serializer):
    from_timestamp = serializers.DateTimeField(required=True)
    to_timestamp = serializers.DateTimeField(required=True)
    offset = serializers.IntegerField(default=0, min_value=0)
    limit = serializers.IntegerField(default=40, min_value=1, max_value=100)
    user_timezone = serializers.ChoiceField(choices=get_timezones(), required=False)
    search = serializers.CharField(required=False, allow_blank=True, default=None)
    search_mode = serializers.ChoiceField(
        required=False,
        default=None,
        choices=ALL_SEARCH_MODES,
    )

    def validate(self, data):
        from_timestamp = data["from_timestamp"]
        to_timestamp = data["to_timestamp"]
        if from_timestamp > to_timestamp:
            raise serializers.ValidationError(
                "from_timestamp must occur before to_timestamp"
            )

        diff = to_timestamp - from_timestamp

        if diff.days > settings.MAX_NUMBER_CALENDAR_DAYS:
            raise serializers.ValidationError(
                "the number of days between from_timestamp and to_timestamp must be "
                f"less than {settings.MAX_NUMBER_CALENDAR_DAYS} days"
            )
        return data


class CalendarViewExampleResponseStackSerializer(serializers.Serializer):
    count = serializers.IntegerField(
        help_text="The total count of rows that are included in this group."
    )
    results = serializers.ListSerializer(
        help_text="All the rows that belong in this group and match provided "
        "`limit` and `offset`.",
        child=get_example_row_serializer_class(example_type="get")(),
    )


def get_calendar_view_example_response_serializer():
    return type(
        "CalendarViewExampleResponseSerializer",
        (serializers.Serializer,),
        {
            "rows": serializers.DictField(
                child=CalendarViewExampleResponseStackSerializer(),
                help_text="Every date bucket (e.g. '2023-01-01') related to the view's date field can "
                "have its own entry like this.",
            ),
            "field_options": serializers.ListSerializer(
                child=CalendarViewFieldOptionsSerializer()
            ),
            "row_metadata": get_example_multiple_rows_metadata_serializer(),
        },
    )
