from django.db import models
from django.utils.translation import gettext_lazy as _

from baserow.contrib.database.api.export.serializers import (
    SUPPORTED_CSV_COLUMN_SEPARATORS,
    SUPPORTED_EXPORT_CHARSETS,
)
from baserow.core.action.registries import (
    ActionCommandType,
    ActionTypeDescription,
    action_type_registry,
    render_action_type_description,
)
from baserow.core.encoders import JSONEncoderSupportingDataClasses
from baserow.core.jobs.models import Job
from baserow.core.mixins import CreatedAndUpdatedOnMixin


class IgnoreMissingKeyDict(dict):
    """
    This dict subclass is used to ignore missing keys when formatting a string.
    """

    def __missing__(self, key):
        return f"%({key})s"


class AuditLogEntry(CreatedAndUpdatedOnMixin, models.Model):
    class CommandType(models.TextChoices):
        DO = ActionCommandType.DO.name, _("DONE")
        UNDO = ActionCommandType.REDO.name, _("UNDONE")
        REDO = ActionCommandType.UNDO.name, _("REDONE")

    user_id = models.PositiveIntegerField(null=True)
    user_email = models.EmailField(null=True, blank=True)

    workspace_id = models.PositiveIntegerField(null=True)
    workspace_name = models.CharField(max_length=165, null=True, blank=True)

    action_uuid = models.CharField(max_length=36, null=True)
    action_type = models.TextField()
    action_timestamp = models.DateTimeField()
    action_params = models.JSONField(
        null=True, encoder=JSONEncoderSupportingDataClasses
    )
    action_command_type = models.CharField(
        max_length=5, choices=CommandType.choices, default=CommandType.DO
    )

    # we don't want break the audit log in case an action is removed or changed.
    # Storing the original description and type in the database we'll always be
    # able to fallback to them and show the original string in case. NOTE: if
    # also the _('$original_description') has been removed from the codebase,
    # the entry won't be translated anymore.
    original_action_short_descr = models.TextField(null=True, blank=True)
    original_action_long_descr = models.TextField(null=True, blank=True)
    original_action_context_descr = models.TextField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True)

    @property
    def type(self):
        try:
            action_type = action_type_registry.get(self.action_type)
        except action_type_registry.does_not_exist_exception_class:
            return _(self.original_action_short_descr)
        return action_type.get_short_description()

    @property
    def description(self):
        try:
            action_type = action_type_registry.get(self.action_type)
            description = action_type.get_long_description(self.params)
        except action_type_registry.does_not_exist_exception_class:
            type_description = ActionTypeDescription(
                self.original_action_short_descr,
                self.original_action_long_descr,
                self.original_action_context_descr,
            )
            description = render_action_type_description(type_description, self.params)

        if self.action_command_type != self.CommandType.DO:
            prefix = self.CommandType[self.action_command_type].label
            return f"{prefix}: {description}"

        return description

    @property
    def params(self):
        return IgnoreMissingKeyDict(self.action_params)

    class Meta:
        ordering = ["-action_timestamp"]
        # The audit log is only ever ordered by `action_timestamp`, so every index
        # below leads with the column that can be filtered on and is followed by the
        # timestamp. That way the filter is a seek instead of a scan, and the rows it
        # finds are already in the requested order, which lets `LIMIT` stop early.
        #
        # A single leading equality column is enough to bound a query that combines
        # several filters: the scan can never be larger than the number of entries
        # for that user, workspace or action type.
        indexes = [
            models.Index(
                fields=["-action_timestamp"],
                name="auditlogentry_ts_idx",
            ),
            models.Index(
                fields=["user_id", "-action_timestamp"],
                name="auditlogentry_user_ts_idx",
            ),
            models.Index(
                fields=["workspace_id", "-action_timestamp"],
                name="auditlogentry_ws_ts_idx",
            ),
            models.Index(
                fields=["action_type", "-action_timestamp"],
                name="auditlogentry_type_ts_idx",
            ),
        ]


class AuditLogExportJob(Job):
    export_charset = models.CharField(
        max_length=32,
        choices=SUPPORTED_EXPORT_CHARSETS,
        default="utf-8",
        help_text="The character set to use when creating the export file.",
    )
    # For ease of use we expect the JSON to contain human typeable forms of each
    # different separator instead of the unicode character itself. By using the
    # DisplayChoiceField we can then map this to the actual separator character by
    # having those be the second value of each choice tuple.
    csv_column_separator = models.CharField(
        max_length=32,
        choices=SUPPORTED_CSV_COLUMN_SEPARATORS,
        default=",",
        help_text="The value used to separate columns in the resulting csv file.",
    )
    csv_first_row_header = models.BooleanField(
        default=True,
        help_text="Whether or not to generate a header row at the top of the csv file.",
    )
    filter_user_id = models.PositiveIntegerField(
        null=True,
        help_text="Optional: The user to filter the audit log by.",
    )
    filter_workspace_id = models.PositiveIntegerField(
        null=True,
        help_text="Optional: The workspace to filter the audit log by.",
    )
    filter_action_type = models.CharField(
        max_length=32,
        null=True,
        help_text="Optional: The event type to filter the audit log by.",
    )
    filter_from_timestamp = models.DateTimeField(
        null=True,
        help_text="Optional: The start datetime to filter the audit log by.",
    )
    filter_to_timestamp = models.DateTimeField(
        null=True,
        help_text="Optional: The end datetime to filter the audit log by.",
    )
    exported_file_name = models.TextField(
        null=True,
        help_text="The CSV file containing the filtered audit log entries.",
    )
    exclude_columns = models.CharField(
        max_length=255,
        null=True,
        help_text="A comma separated list of column names to exclude from the export.",
    )

    @property
    def workspace_id(self):
        # FIXME: Temporarily setting the current workspace ID for URL generation in
        # storage backends, enabling permission checks at download time.
        if not self.user.is_staff:
            return self.filter_workspace_id
