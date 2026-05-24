from rest_framework import serializers

from baserow.contrib.database.fields.models import Field
from baserow.core.jobs.registries import job_type_registry
from baserow_enterprise.data_scanner.constants import (
    SCAN_TYPE_LIST_OF_VALUES,
    SCAN_TYPE_LIST_TABLE,
    SCAN_TYPE_PATTERN,
    SCANNABLE_FIELD_CONTENT_TYPES,
)
from baserow_enterprise.data_scanner.job_types import DataScanResultExportJobType
from baserow_enterprise.data_scanner.models import DataScan, DataScanResult


class DataScanSerializer(serializers.ModelSerializer):
    workspace_ids = serializers.SerializerMethodField()
    list_items = serializers.SerializerMethodField()
    source_table_id = serializers.SerializerMethodField()
    source_field_id = serializers.SerializerMethodField()
    source_workspace_id = serializers.SerializerMethodField()
    source_database_id = serializers.SerializerMethodField()
    results_count = serializers.SerializerMethodField()

    class Meta:
        model = DataScan
        fields = [
            "id",
            "name",
            "scan_type",
            "pattern",
            "frequency",
            "scan_all_workspaces",
            "workspace_ids",
            "is_running",
            "last_run_started_at",
            "last_run_finished_at",
            "last_error",
            "list_items",
            "results_count",
            "source_table_id",
            "source_field_id",
            "whole_words",
            "source_workspace_id",
            "source_database_id",
            "created_on",
            "updated_on",
        ]

    def get_workspace_ids(self, obj):
        return [ws.id for ws in obj.workspaces.all()]

    def get_list_items(self, obj):
        return [item.value for item in obj.list_items.all()]

    def get_source_table_id(self, obj):
        return obj.source_table_id

    def get_source_field_id(self, obj):
        return obj.source_field_id

    def get_source_workspace_id(self, obj):
        try:
            return obj.source_table.database.workspace_id
        except AttributeError:
            return None

    def get_source_database_id(self, obj):
        try:
            return obj.source_table.database_id
        except AttributeError:
            return None

    def get_results_count(self, obj):
        if hasattr(obj, "results_count"):
            return obj.results_count
        return obj.results.count()


class DataScanWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    scan_type = serializers.ChoiceField(
        choices=DataScan.SCAN_TYPE_CHOICES,
        required=False,
    )
    pattern = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True
    )
    frequency = serializers.ChoiceField(
        choices=DataScan.FREQUENCY_CHOICES,
        required=False,
    )
    scan_all_workspaces = serializers.BooleanField(required=False)
    workspace_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
    )
    list_items = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )
    source_table_id = serializers.IntegerField(required=False, allow_null=True)
    source_field_id = serializers.IntegerField(required=False, allow_null=True)
    whole_words = serializers.BooleanField(required=False)

    def validate_source_field_id(self, value):
        if value is not None:
            try:
                field = Field.objects.get(id=value)
            except Field.DoesNotExist:
                raise serializers.ValidationError(
                    "The specified source field does not exist."
                )
            if field.content_type.model not in SCANNABLE_FIELD_CONTENT_TYPES:
                raise serializers.ValidationError(
                    "The specified source field type is not compatible with data "
                    "scanning."
                )
        return value


class DataScanCreateSerializer(DataScanWriteSerializer):
    name = serializers.CharField(max_length=255)
    scan_type = serializers.ChoiceField(
        choices=DataScan.SCAN_TYPE_CHOICES,
    )
    workspace_ids = serializers.ListField(
        child=serializers.IntegerField(),
        default=list,
    )
    list_items = serializers.ListField(
        child=serializers.CharField(),
        default=list,
    )
    pattern = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=None
    )
    frequency = serializers.ChoiceField(
        choices=DataScan.FREQUENCY_CHOICES,
        default="manual",
    )
    scan_all_workspaces = serializers.BooleanField(default=True)
    whole_words = serializers.BooleanField(default=True)

    def validate(self, data):
        scan_type = data.get("scan_type")
        if scan_type == SCAN_TYPE_PATTERN and not data.get("pattern"):
            raise serializers.ValidationError(
                {"pattern": "Pattern is required for pattern scan type."}
            )
        if scan_type == SCAN_TYPE_LIST_OF_VALUES and not data.get("list_items"):
            raise serializers.ValidationError(
                {"list_items": "List items are required for list of values scan type."}
            )
        if scan_type == SCAN_TYPE_LIST_TABLE:
            if not data.get("source_table_id") or not data.get("source_field_id"):
                raise serializers.ValidationError(
                    {
                        "source_table_id": "Source table and field are required for list table scan type."
                    }
                )
        return data


class DataScanUpdateSerializer(DataScanWriteSerializer):
    pass


class DataScanResultSerializer(serializers.ModelSerializer):
    scan_name = serializers.SerializerMethodField()
    workspace_name = serializers.SerializerMethodField()
    database_id = serializers.SerializerMethodField()
    database_name = serializers.SerializerMethodField()
    table_name = serializers.SerializerMethodField()
    field_name = serializers.SerializerMethodField()

    class Meta:
        model = DataScanResult
        fields = [
            "id",
            "scan_id",
            "scan_name",
            "workspace_name",
            "database_id",
            "database_name",
            "table_id",
            "table_name",
            "field_name",
            "row_id",
            "matched_value",
            "first_identified_on",
            "last_identified_on",
        ]

    def get_scan_name(self, obj):
        return obj.scan.name

    def get_workspace_name(self, obj):
        try:
            return obj.field.table.database.workspace.name
        except AttributeError:
            return None

    def get_database_id(self, obj):
        return obj.table.database_id

    def get_database_name(self, obj):
        try:
            return obj.field.table.database.name
        except AttributeError:
            return None

    def get_table_name(self, obj):
        try:
            return obj.field.table.name
        except AttributeError:
            return None

    def get_field_name(self, obj):
        try:
            return obj.field.name
        except AttributeError:
            return None


class WorkspaceStructureFieldSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.SerializerMethodField()

    def get_type(self, obj):
        field_type = obj.content_type.model
        if field_type.endswith("field"):
            field_type = field_type[: -len("field")]
        return field_type


class WorkspaceStructureTableSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["fields"] = WorkspaceStructureFieldSerializer(
            instance.field_set.all(), many=True
        ).data
        return data


class WorkspaceStructureDatabaseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    tables = serializers.SerializerMethodField()

    def get_tables(self, obj):
        return WorkspaceStructureTableSerializer(obj.table_set.all(), many=True).data


DataScanResultExportJobRequestSerializer = job_type_registry.get(
    DataScanResultExportJobType.type
).get_serializer_class(
    base_class=serializers.Serializer,
    request_serializer=True,
    meta_ref_name="SingleDataScanResultExportJobRequestSerializer",
)

DataScanResultExportJobResponseSerializer = job_type_registry.get(
    DataScanResultExportJobType.type
).get_serializer_class(
    base_class=serializers.Serializer,
    meta_ref_name="SingleDataScanResultExportJobResponseSerializer",
)
