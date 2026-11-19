from rest_framework import serializers

from baserow.core.models import Snapshot, User

# The largest value the max snapshots columns can store.
POSITIVE_INTEGER_FIELD_MAX = 2147483647


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username",)


class SnapshotAllowanceSerializer(serializers.Serializer):
    used = serializers.IntegerField(
        help_text="How much of the workspace's snapshot allowance its applications "
        "reserve: the sum of their max snapshots."
    )
    limit = serializers.IntegerField(
        allow_null=True,
        help_text="The snapshot allowance of the workspace, or `null` when there is "
        "no limit. `0` means snapshots are disabled.",
    )
    over_allowance = serializers.BooleanField(
        help_text="Whether the applications reserve more than the allowance."
    )
    blocked = serializers.BooleanField(
        help_text="Whether new snapshots are refused in the workspace, for example "
        "because it's been over its allowance for too long."
    )
    can_exceed_allowance = serializers.BooleanField(
        help_text="Whether raising a max can take the workspace over its allowance. "
        "New snapshots are then refused once it's been over for too long."
    )
    snapshot_count = serializers.IntegerField(
        help_text="The number of snapshots the workspace holds."
    )
    default_max_snapshots = serializers.IntegerField(
        help_text="The max snapshots of applications that don't have their own."
    )
    max_snapshots_limit = serializers.IntegerField(
        allow_null=True,
        help_text="The most snapshots one application can keep, or `null` when "
        "there is no maximum.",
    )
    expiration_days = serializers.IntegerField(
        help_text="The number of days after which a snapshot is deleted."
    )


class SnapshotUsageSerializer(SnapshotAllowanceSerializer):
    max_snapshots = serializers.IntegerField(
        allow_null=True,
        help_text="The max snapshots of the application, or `null` when it follows the "
        "workspace default max snapshots.",
    )
    effective_max_snapshots = serializers.IntegerField(
        help_text="How many snapshots the application keeps."
    )
    application_snapshot_count = serializers.IntegerField(
        help_text="The number of snapshots the application holds."
    )
    protected_count = serializers.IntegerField(
        help_text="The number of protected snapshots the application holds."
    )


class UpdateApplicationMaxSnapshotsSerializer(serializers.Serializer):
    max_snapshots = serializers.IntegerField(
        min_value=0,
        max_value=POSITIVE_INTEGER_FIELD_MAX,
        allow_null=True,
        help_text="How many snapshots the application keeps, or `null` to follow "
        "the workspace default max snapshots.",
    )
    delete_snapshots = serializers.BooleanField(
        default=False,
        help_text="Confirms that the oldest unprotected snapshots beyond a lowered "
        "max snapshots are deleted.",
    )


class WorkspaceSnapshotApplicationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    max_snapshots = serializers.IntegerField(
        allow_null=True,
        help_text="The max snapshots of the application, or `null` when it follows the "
        "workspace default max snapshots.",
    )
    snapshot_count = serializers.IntegerField()
    protected_count = serializers.IntegerField()


class WorkspaceSnapshotSettingsSerializer(SnapshotAllowanceSerializer):
    applications = WorkspaceSnapshotApplicationSerializer(
        many=True,
        help_text="The applications of the workspace that the user can see.",
    )


class UpdateWorkspaceSnapshotSettingsSerializer(serializers.Serializer):
    default_max_snapshots = serializers.IntegerField(
        min_value=0,
        max_value=POSITIVE_INTEGER_FIELD_MAX,
        help_text="The max snapshots of applications that don't have their own.",
    )
    delete_snapshots = serializers.BooleanField(
        default=False,
        help_text="Confirms that the oldest unprotected snapshots beyond a lowered "
        "max snapshots are deleted.",
    )


class UpdateSnapshotSerializer(serializers.Serializer):
    protected = serializers.BooleanField(
        help_text="A protected snapshot is never deleted automatically."
    )


class SnapshotSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Snapshot
        fields = [
            "id",
            "name",
            "snapshot_from_application",
            "created_at",
            "created_by",
            "created_automatically",
            "protected",
        ]
        read_only_fields = [
            "id",
            "snapshot_from_application",
            "created_at",
            "created_by",
            "created_automatically",
            "protected",
        ]


class CreateSnapshotSerializer(serializers.ModelSerializer):
    raise_max_snapshots = serializers.BooleanField(
        default=False,
        help_text="Raises the max snapshots of the application by one first when it "
        "has no room for another snapshot: it keeps none, or every snapshot it keeps "
        "is protected. Needs permission to change its max snapshots.",
    )
    protected = serializers.BooleanField(
        default=True,
        help_text="Whether the new snapshot is protected. A protected snapshot is "
        "never deleted automatically. An unprotected one can be replaced by a later "
        "snapshot once the application is at its max snapshots.",
    )

    class Meta:
        model = Snapshot
        fields = ["name", "raise_max_snapshots", "protected"]
