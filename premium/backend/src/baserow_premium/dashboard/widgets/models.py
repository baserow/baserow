from django.db import models

from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationSeries,
)

from baserow.contrib.dashboard.widgets.models import Widget


class ChartWidget(Widget):
    data_source = models.ForeignKey(
        "dashboard.DashboardDataSource",
        on_delete=models.PROTECT,
        help_text="Data source for fetching the result to display.",
    )


class ChartSeriesChartType(models.TextChoices):
    BAR = "BAR", "Bar"
    LINE = "LINE", "Line"


class ChartSeriesConfig(models.Model):
    widget = models.ForeignKey(
        ChartWidget, on_delete=models.CASCADE, related_name="series_config"
    )
    series = models.ForeignKey(
        LocalBaserowTableServiceAggregationSeries, on_delete=models.CASCADE
    )
    series_chart_type = models.CharField(
        max_length=4,
        choices=ChartSeriesChartType.choices,
        default=ChartSeriesChartType.BAR,
        help_text="Type of chart to display (Bar or Line).",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["series"], name="unique_series")]
