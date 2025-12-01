import pytz
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.builder.elements.models import Element

IANA_TIMEZONES = [(tz, tz) for tz in pytz.all_timezones]


class DispatchDataSourceDataSourceContextSerializer(serializers.Serializer):
    element = serializers.PrimaryKeyRelatedField(
        required=False,
        default=None,
        allow_null=True,
        queryset=Element.objects.select_related("page__builder").all(),
        help_text="Optionally provide an `element` to the data source. Currently only "
        "used in element-level filtering, sorting and searching if the "
        "element is a collection element.",
    )

    def validate(self, data):
        """
        Responsible for validating the data source dispatch request. Ensures that
        the dispatched element belongs to the same page as the data source.
        """

        page = self.context.get("page")
        element = data.get("element")
        if element:
            if (
                element.page_id != page.id
                and element.page.builder.shared_page.id != page.id
            ):
                raise ValidationError(
                    "The data source is not available for the dispatched element.",
                    code="PAGE_MISMATCH",
                )

        return data


class DispatchDataSourceUserContextSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        help_text="Current user id.", required=False, allow_null=True
    )
    timezone = serializers.ChoiceField(
        help_text="An IANA timezone name.",
        required=False,
        allow_null=True,
        choices=IANA_TIMEZONES,
    )
