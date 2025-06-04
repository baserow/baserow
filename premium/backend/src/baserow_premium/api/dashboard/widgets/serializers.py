from baserow_premium.dashboard.widgets.models import ChartSeriesChartType
from rest_framework import serializers


class ChartSeriesConfigSerializer(serializers.Serializer):
    series_id = serializers.IntegerField()
    series_chart_type = serializers.ChoiceField(choices=ChartSeriesChartType.choices)
