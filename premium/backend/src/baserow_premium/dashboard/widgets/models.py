from django.db import models

from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationSeries,
)

from baserow.contrib.dashboard.widgets.models import Widget


class ChartSeriesChartType(models.TextChoices):
    BAR = "BAR", "Bar"
    LINE = "LINE", "Line"


class ChartWidget(Widget):
    data_source = models.ForeignKey(
        "dashboard.DashboardDataSource",
        on_delete=models.PROTECT,
        help_text="Data source for fetching the result to display.",
    )
    default_series_chart_type = models.CharField(
        max_length=4,
        choices=ChartSeriesChartType.choices,
        default=ChartSeriesChartType.BAR,
        db_default=ChartSeriesChartType.BAR,
        help_text="Default chart type.",
    )


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


class PieChartSeriesChartType(models.TextChoices):
    PIE = "PIE", "Pie"
    DOUGHNUT = "DOUGHNUT", "Doughnut"


class PieChartWidget(Widget):
    data_source = models.ForeignKey(
        "dashboard.DashboardDataSource",
        on_delete=models.PROTECT,
        help_text="Data source for fetching the result to display.",
    )
    default_series_chart_type = models.CharField(
        max_length=10,
        choices=PieChartSeriesChartType.choices,
        default=PieChartSeriesChartType.PIE,
        db_default=PieChartSeriesChartType.PIE,
        help_text="Default chart type.",
    )


class PieChartSeriesConfig(models.Model):
    widget = models.ForeignKey(
        PieChartWidget, on_delete=models.CASCADE, related_name="series_config"
    )
    series = models.ForeignKey(
        LocalBaserowTableServiceAggregationSeries, on_delete=models.CASCADE
    )
    series_chart_type = models.CharField(
        max_length=10,
        choices=PieChartSeriesChartType.choices,
        default=PieChartSeriesChartType.PIE,
        help_text="Type of chart to display (Pie, Doughnut).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["series"], name="pie_chart_unique_series")
        ]
