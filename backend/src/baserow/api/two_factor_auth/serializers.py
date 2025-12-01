from django.utils.functional import lazy

from rest_framework import serializers

from baserow.core.two_factor_auth.models import TwoFactorAuthProviderModel
from baserow.core.two_factor_auth.registries import two_factor_auth_type_registry


class TwoFactorAuthSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField(read_only=True)
    is_enabled = serializers.BooleanField(read_only=True)

    def get_type(self, instance):
        return instance.get_type().type

    class Meta:
        model = TwoFactorAuthProviderModel
        fields = ["type", "is_enabled"]


class CreateTwoFactorAuthSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(two_factor_auth_type_registry.get_types, list)(),
        required=True,
        help_text="The type of the two factor auth.",
    )

    class Meta:
        model = TwoFactorAuthProviderModel
        fields = ["type"]


class DisableTwoFactorAuthSerializer(serializers.Serializer):
    password = serializers.CharField(required=True)


class VerifyTOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(required=False)
    backup_code = serializers.CharField(required=False)
