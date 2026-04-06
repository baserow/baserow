from django.conf import settings
from django.db import models

from baserow.contrib.database.api.export.serializers import (
    SUPPORTED_CSV_COLUMN_SEPARATORS,
    SUPPORTED_EXPORT_CHARSETS,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.core.jobs.models import Job
from baserow.core.models import Workspace
from baserow_enterprise.data_scanner.constants import (
    SCAN_TYPE_LIST_OF_VALUES,
    SCAN_TYPE_LIST_TABLE,
    SCAN_TYPE_PATTERN,
)


class DataScan(models.Model):
    SCAN_TYPE_CHOICES = [
        (SCAN_TYPE_PATTERN, "Pattern"),
        (SCAN_TYPE_LIST_OF_VALUES, "List of values"),
        (SCAN_TYPE_LIST_TABLE, "List Table"),
    ]

    FREQUENCY_CHOICES = [
        ("manual", "Manual"),
        ("hourly", "Hourly"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
    ]

    name = models.CharField(max_length=255)
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPE_CHOICES)
    pattern = models.TextField(null=True, blank=True)
    frequency = models.CharField(
        max_length=10, choices=FREQUENCY_CHOICES, default="manual"
    )
    scan_all_workspaces = models.BooleanField(default=True)
    workspaces = models.ManyToManyField(Workspace, blank=True)
    is_running = models.BooleanField(default=False)
    last_run_started_at = models.DateTimeField(null=True, blank=True)
    last_run_finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    source_table = models.ForeignKey(
        Table, on_delete=models.SET_NULL, null=True, blank=True
    )
    source_field = models.ForeignKey(
        Field, on_delete=models.SET_NULL, null=True, blank=True
    )
    whole_words = models.BooleanField(db_default=True, default=True)

    class Meta:
        ordering = ["-created_on"]

    def __str__(self):
        return self.name


class DataScanListItem(models.Model):
    scan = models.ForeignKey(
        DataScan, on_delete=models.CASCADE, related_name="list_items"
    )
    value = models.TextField()

    def __str__(self):
        return self.value


class DataScanResult(models.Model):
    scan = models.ForeignKey(DataScan, on_delete=models.CASCADE, related_name="results")
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    field = models.ForeignKey(Field, on_delete=models.CASCADE)
    row_id = models.IntegerField()
    matched_value = models.TextField()
    first_identified_on = models.DateTimeField(db_index=True)
    last_identified_on = models.DateTimeField()

    class Meta:
        unique_together = [("scan", "table", "row_id", "field")]
        ordering = ["-first_identified_on"]
        indexes = [
            models.Index(fields=["scan", "first_identified_on"]),
        ]

    def __str__(self):
        return f"Result(scan={self.scan_id}, table={self.table_id}, row={self.row_id})"


class DataScanResultExportJob(Job):
    export_charset = models.CharField(
        max_length=32,
        choices=SUPPORTED_EXPORT_CHARSETS,
        default="utf-8",
    )
    csv_column_separator = models.CharField(
        max_length=32,
        choices=SUPPORTED_CSV_COLUMN_SEPARATORS,
        default=",",
    )
    csv_first_row_header = models.BooleanField(default=True)
    filter_scan_id = models.PositiveIntegerField(null=True)
    exported_file_name = models.TextField(null=True)
