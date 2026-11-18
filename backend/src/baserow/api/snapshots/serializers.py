from rest_framework import serializers

from baserow.core.models import Snapshot, User

# The largest value the keep columns can store.
MAX_KEEP = 2147483647


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username",)


class SnapshotAllowanceSerializer(serializers.Serializer):
    used = serializers.IntegerField(
        help_text="How much of the workspace's snapshot allowance its applications "
        "reserve: the sum of their keeps."
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
        help_text="Whether raising a keep can take the workspace over its allowance. "
        "New snapshots are then refused once it's been over for too long."
    )
    snapshot_count = serializers.IntegerField(
        help_text="The number of snapshots the workspace holds."
    )
    default_keep = serializers.IntegerField(
        help_text="How many snapshots applications without a keep of their own keep."
    )
    max_keep = serializers.IntegerField(
        allow_null=True,
        help_text="The most snapshots one application can keep, or `null` when "
        "there is no maximum.",
    )
    expiration_days = serializers.IntegerField(
        help_text="The number of days after which a snapshot is deleted."
    )


class SnapshotUsageSerializer(SnapshotAllowanceSerializer):
    keep = serializers.IntegerField(
        allow_null=True,
        help_text="The keep of the application, or `null` when it follows the "
        "workspace default keep.",
    )
    effective_keep = serializers.IntegerField(
        help_text="How many snapshots the application keeps."
    )
    application_snapshot_count = serializers.IntegerField(
        help_text="The number of snapshots the application holds."
    )
    protected_count = serializers.IntegerField(
        help_text="The number of protected snapshots the application holds."
    )


class UpdateApplicationSnapshotKeepSerializer(serializers.Serializer):
    keep = serializers.IntegerField(
        min_value=0,
        max_value=MAX_KEEP,
        allow_null=True,
        help_text="How many snapshots the application keeps, or `null` to follow "
        "the workspace default keep.",
    )
    delete_snapshots = serializers.BooleanField(
        default=False,
        help_text="Confirms that the oldest unprotected snapshots beyond a lowered "
        "keep are deleted.",
    )


class WorkspaceSnapshotApplicationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    keep = serializers.IntegerField(
        allow_null=True,
        help_text="The keep of the application, or `null` when it follows the "
        "workspace default keep.",
    )
    snapshot_count = serializers.IntegerField()
    protected_count = serializers.IntegerField()


class WorkspaceSnapshotSettingsSerializer(SnapshotAllowanceSerializer):
    applications = WorkspaceSnapshotApplicationSerializer(
        many=True,
        help_text="The applications of the workspace that the user can see.",
    )


class UpdateWorkspaceSnapshotSettingsSerializer(serializers.Serializer):
    default_keep = serializers.IntegerField(
        min_value=0,
        max_value=MAX_KEEP,
        help_text="How many snapshots applications without a keep of their own keep.",
    )
    delete_snapshots = serializers.BooleanField(
        default=False,
        help_text="Confirms that the oldest unprotected snapshots beyond a lowered "
        "keep are deleted.",
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
    raise_keep = serializers.BooleanField(
        default=False,
        help_text="Raises the keep of the application by one first when it has no "
        "room for another snapshot: it keeps none, or every snapshot it keeps is "
        "protected. Needs permission to change its keep.",
    )

    class Meta:
        model = Snapshot
        fields = ["name", "raise_keep"]
