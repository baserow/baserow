from copy import deepcopy

from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.validators import no_url_validation
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.models import User


class IdentitySerializer(serializers.ModelSerializer):
    user_type = serializers.CharField(source="profile.user_type", read_only=True)
    workspace_id = serializers.SerializerMethodField()
    name = serializers.CharField(source="first_name", read_only=True)
    role_uid = serializers.SerializerMethodField()
    last_active = serializers.DateTimeField(
        source="profile.last_active", read_only=True
    )
    created_on = serializers.DateTimeField(source="date_joined", read_only=True)

    def get_workspace_id(self, identity):
        return IdentityHandler.get_workspace(identity).id

    def get_role_uid(self, identity):
        return IdentityHandler.get_role_uid(identity)

    def get_fields(self):
        fields = super().get_fields()
        for extension in identity_extension_type_registry.get_all():
            fields.update(deepcopy(extension.response_fields))
        return fields

    class Meta:
        model = User
        fields = (
            "id",
            "user_type",
            "workspace_id",
            "name",
            "role_uid",
            "last_active",
            "created_on",
        )


class IdentityListSerializer(IdentitySerializer):
    """
    An identity of the list of identities, for the API documentation, with the fields the
    identity extensions add to every identity of a list response.
    """

    def get_fields(self):
        fields = super().get_fields()
        for extension in identity_extension_type_registry.get_all():
            fields.update(deepcopy(extension.list_response_fields))
        return fields


class IdentityRequestSerializer(
    UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer
):
    name = serializers.CharField(max_length=150, validators=[no_url_validation])
    role_uid = serializers.CharField(max_length=32, required=False)

    def get_fields(self):
        fields = super().get_fields()
        for extension in identity_extension_type_registry.get_all():
            fields.update(deepcopy(extension.request_fields))
        return fields


class UpdateIdentityRequestSerializer(IdentityRequestSerializer):
    name = serializers.CharField(
        max_length=150, required=False, validators=[no_url_validation]
    )


class IdentityListParamsSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, default=1)
    size = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_null=True, default=None)
    sorts = serializers.CharField(required=False, allow_null=True, default=None)
