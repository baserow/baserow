from django.db import models


class ChartSeriesChartType(models.TextChoices):
    BAR = "BAR", "Bar"
    LINE = "LINE", "Line"
