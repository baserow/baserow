from rest_framework import serializers

from baserow_premium.charts import ChartSeriesChartType
from baserow_premium.dashboard.widgets.models import (
    PieChartSeriesChartType,
)


class SeriesColorSerializer(serializers.Serializer):
    series_color = serializers.RegexField(
        regex=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
        required=False,
        allow_null=True,
    )

    def to_representation(self, instance):
        result = super().to_representation(instance)
        if result.get("series_color") is None:
            result.pop("series_color", None)
        return result


class ChartSeriesConfigSerializer(SeriesColorSerializer):
    series_id = serializers.IntegerField()
    series_chart_type = serializers.ChoiceField(choices=ChartSeriesChartType.choices)


class PieChartSeriesConfigSerializer(SeriesColorSerializer):
    series_id = serializers.IntegerField()
    series_chart_type = serializers.ChoiceField(choices=PieChartSeriesChartType.choices)
