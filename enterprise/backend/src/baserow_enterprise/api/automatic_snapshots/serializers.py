from rest_framework import serializers

from baserow.contrib.integrations.core.constants import PERIODIC_INTERVAL_CHOICES
from baserow_enterprise.automatic_snapshots.models import AutomaticSnapshotSchedule

AUTOMATIC_SNAPSHOT_SCHEDULE_WRITABLE_FIELDS = [
    "enabled",
    "interval",
    "timezone",
    "minute",
    "hour",
    "day_of_week",
    "day_of_month",
]


class AutomaticSnapshotScheduleSerializer(serializers.ModelSerializer):
    application_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = AutomaticSnapshotSchedule
        fields = [
            "id",
            "application_id",
            *AUTOMATIC_SNAPSHOT_SCHEDULE_WRITABLE_FIELDS,
            "next_run_at",
            "last_run_at",
            "last_error",
            "paused_reason",
        ]
        read_only_fields = fields


class CreateAutomaticSnapshotScheduleSerializer(serializers.ModelSerializer):
    interval = serializers.ChoiceField(choices=PERIODIC_INTERVAL_CHOICES)

    class Meta:
        model = AutomaticSnapshotSchedule
        fields = AUTOMATIC_SNAPSHOT_SCHEDULE_WRITABLE_FIELDS


class UpdateAutomaticSnapshotScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomaticSnapshotSchedule
        fields = AUTOMATIC_SNAPSHOT_SCHEDULE_WRITABLE_FIELDS
        extra_kwargs = {
            field: {"required": False}
            for field in AUTOMATIC_SNAPSHOT_SCHEDULE_WRITABLE_FIELDS
        }


class ApplicationAutomaticSnapshotOverviewSerializer(serializers.Serializer):
    state = serializers.ChoiceField(
        choices=["workspace_default", "own_schedule", "off"],
        help_text="`workspace_default` when the application follows the workspace "
        "default, `own_schedule` when it has an enabled schedule of its own, and "
        "`off` when its own schedule is turned off.",
    )
    schedule = AutomaticSnapshotScheduleSerializer(
        allow_null=True, help_text="The schedule of the application, if it has one."
    )
    workspace_default = AutomaticSnapshotScheduleSerializer(
        allow_null=True,
        help_text="The workspace default schedule, if the workspace has one.",
    )
    min_interval_minutes = serializers.IntegerField(
        help_text="The shortest interval, in minutes, a schedule can run at."
    )


class WorkspaceAutomaticSnapshotSchedulesSerializer(serializers.Serializer):
    workspace_default = AutomaticSnapshotScheduleSerializer(allow_null=True)
    application_schedules = AutomaticSnapshotScheduleSerializer(
        many=True,
        help_text="The schedules of the applications that have one of their own. "
        "A disabled one opts its application out of the workspace default.",
    )
    min_interval_minutes = serializers.IntegerField(
        help_text="The shortest interval, in minutes, a schedule can run at."
    )


class BulkAutomaticSnapshotScheduleSerializer(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, max_length=200
    )
    action = serializers.ChoiceField(
        choices=["apply", "reset"],
        help_text="`apply` gives every application its own copy of the schedule. "
        "`reset` deletes their own schedules, so they follow the workspace default.",
    )
    schedule = CreateAutomaticSnapshotScheduleSerializer(required=False)

    def validate(self, data):
        if data["action"] == "apply" and "schedule" not in data:
            raise serializers.ValidationError(
                {"schedule": "A schedule is required to apply it."}
            )
        return data
