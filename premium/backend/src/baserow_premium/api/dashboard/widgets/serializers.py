from baserow_premium.dashboard.widgets.models import (
    ChartSeriesChartType,
    PieChartSeriesChartType,
)
from rest_framework import serializers


class ChartSeriesConfigSerializer(serializers.Serializer):
    series_id = serializers.IntegerField()
    series_chart_type = serializers.ChoiceField(choices=ChartSeriesChartType.choices)


class PieChartSeriesConfigSerializer(serializers.Serializer):
    series_id = serializers.IntegerField()
    series_chart_type = serializers.ChoiceField(choices=PieChartSeriesChartType.choices)
