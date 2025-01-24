from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.auth_provider.models import AuthProviderModel
from baserow.core.auth_provider.validators import validate_domain
from baserow.core.registries import auth_provider_type_registry


class AuthProviderSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField(help_text="The type of the related field.")

    domain = serializers.CharField(
        validators=[validate_domain],
        required=True,
        help_text=AuthProviderModel._meta.get_field("domain").help_text,
    )

    class Meta:
        model = AuthProviderModel
        fields = ("id", "type", "domain", "enabled")
        extra_kwargs = {
            "id": {"read_only": True},
            "type": {"read_only": True},
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return auth_provider_type_registry.get_by_model(instance.specific_class).type
