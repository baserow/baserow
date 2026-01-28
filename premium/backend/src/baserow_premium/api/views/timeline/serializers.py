from rest_framework import serializers

from baserow_premium.views.models import TimelineViewFieldOptions


class TimelineViewFieldOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimelineViewFieldOptions
        fields = (
            "hidden",
            "order",
        )
