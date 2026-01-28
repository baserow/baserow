from drf_spectacular.openapi import OpenApiSerializerFieldExtension
from rest_framework import serializers

from baserow.contrib.database.models import Database
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tokens.models import Token

from .schemas import token_permissions_field_schema


class TokenPermissionsField(serializers.Field):
    default_error_messages = {
        "invalid_key": "Only create, read, update and delete keys are allowed.",
        "invalid_value": (
            "The value must either be a bool, or a list containing database or table "
            'ids like [["database", 1], ["table", 1]].'
        ),
        "invalid_instance_type": "The instance type can only be a database or table.",
        "invalid_table_id": "The table id {instance_id} is not valid.",
        "invalid_database_id": "The database id {instance_id} is not valid.",
    }
    valid_types = ["create", "read", "update", "delete"]

    def __init__(self, **kwargs):
        kwargs["source"] = "*"
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        """
        Validates if the provided data structure is correct and replaces the database
        and table references with selected instances. The following data format is
        expected:

        {
            "create": True,
            "read": [['database', ID], ['table', ID]],
            "update": False,
            "delete": True
        }

        which will be converted to:

        {
            "create": True,
            "read": [Database(ID), Table(ID)],
            "update": False,
            "delete": True
        }

        :param data: The non validated permissions containing references to the
            database and tables.
        :type data: dict
        :return: The validated permissions with objects instead of references.
        :rtype: dict
        """

        tables = {}
        databases = {}

        if not isinstance(data, dict) or len(data) != len(self.valid_types):
            self.fail("invalid_key")

        for key, value in data.items():
            if key not in self.valid_types:
                self.fail("invalid_key")

            if not isinstance(value, bool) and not isinstance(value, list):
                self.fail("invalid_value")

            if isinstance(value, list):
                for instance in value:
                    if (
                        not isinstance(instance, list)
                        or not len(instance) == 2
                        or not isinstance(instance[0], str)
                        or not isinstance(instance[1], int)
                    ):
                        self.fail("invalid_value")

                    instance_type, instance_id = instance
                    if instance_type == "database":
                        databases[instance_id] = None
                    elif instance_type == "table":
                        tables[instance_id] = None
                    else:
                        self.fail("invalid_instance_type")

        if len(tables) > 0:
            tables = {
                table.id: table
                for table in Table.objects.filter(id__in=tables.keys()).select_related(
                    "database"
                )
            }

        if len(databases) > 0:
            databases = {
                database.id: database
                for database in Database.objects.filter(id__in=databases.keys())
            }

        for key, value in data.items():
            if isinstance(value, list):
                for index, (instance_type, instance_id) in enumerate(value):
                    if instance_type == "database":
                        if instance_id not in databases:
                            self.fail("invalid_database_id", instance_id=instance_id)
                        data[key][index] = databases[instance_id]
                    elif instance_type == "table":
                        if instance_id not in tables:
                            self.fail("invalid_table_id", instance_id=instance_id)
                        data[key][index] = tables[instance_id]

        return {
            "create": data["create"],
            "read": data["read"],
            "update": data["update"],
            "delete": data["delete"],
        }

    def to_representation(self, value):
        """
        If the provided value is a Token instance we need to fetch the permissions from
        the database and format them the correct way.

        If the provided value is a dict it means the permissions have already been
        provided and validated once, so we can just return that value. The variant is
        used when we want to validate the input.

        :param value: The prepared value that needs to be serialized.
        :type value: Token or dict
        :return: A dict containing the create, read, update and delete permissions
        :rtype: dict
        """

        if isinstance(value, Token):
            permissions = {
                "create": False,
                "read": False,
                "update": False,
                "delete": False,
            }

            for permission in value.tokenpermission_set.all():
                if permissions[permission.type] is True:
                    continue

                if permission.database_id is None and permission.table_id is None:
                    permissions[permission.type] = True
                else:
                    if not isinstance(permissions[permission.type], list):
                        permissions[permission.type] = []
                    if permission.database_id is not None:
                        permissions[permission.type].append(
                            ("database", permission.database_id)
                        )
                    elif permission.table_id is not None:
                        permissions[permission.type].append(
                            ("table", permission.table_id)
                        )

            return permissions
        else:
            permissions = {}
            for type_name in self.valid_types:
                if type_name not in value:
                    return None
                permissions[type_name] = value[type_name]
            return permissions


class TokenPermissionsFieldFix(OpenApiSerializerFieldExtension):
    target_class = (
        "baserow.contrib.database.api.tokens.serializers.TokenPermissionsField"
    )

    def map_serializer_field(self, auto_schema, direction):
        return token_permissions_field_schema


class TokenSerializer(serializers.ModelSerializer):
    permissions = TokenPermissionsField()

    class Meta:
        model = Token
        fields = (
            "id",
            "name",
            "workspace",
            "key",
            "permissions",
        )
        extra_kwargs = {
            "id": {"read_only": True},
        }


class TokenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Token
        fields = (
            "name",
            "workspace",
        )


class TokenUpdateSerializer(serializers.ModelSerializer):
    permissions = TokenPermissionsField(required=False)
    rotate_key = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Indicates if a new key must be generated.",
    )

    class Meta:
        model = Token
        fields = ("name", "permissions", "rotate_key")
        extra_kwargs = {
            "name": {"required": False},
        }
