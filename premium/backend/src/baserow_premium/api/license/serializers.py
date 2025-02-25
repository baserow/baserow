from functools import lru_cache
from typing import Optional

from django.contrib.auth import get_user_model

from baserow_premium.license.models import License
from baserow_premium.license.registries import SeatUsageSummary
from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

User = get_user_model()


class LicenseSerializer(serializers.ModelSerializer):
    license_id = serializers.CharField(help_text="Unique identifier of the license.")
    is_active = serializers.BooleanField(
        help_text="Indicates if the backend deems the license valid."
    )
    valid_from = serializers.DateTimeField(
        help_text="From which timestamp the license becomes active."
    )
    valid_through = serializers.DateTimeField(
        help_text="Until which timestamp the license is active."
    )
    free_users_count = serializers.SerializerMethodField(
        help_text="The amount of free users that are currently using the license."
    )
    seats_taken = serializers.SerializerMethodField(
        help_text="The amount of users that are currently using the license."
    )
    seats = serializers.IntegerField(
        help_text="The maximum amount of users that can use the license."
    )
    application_users = serializers.IntegerField(
        help_text="The amount of application builder users permitted in this license."
    )
    application_users_taken = serializers.SerializerMethodField(
        help_text="The amount of application builder users used so far in this license."
    )
    product_code = serializers.CharField(
        help_text="The product code that indicates what the license unlocks."
    )
    issued_on = serializers.DateTimeField(
        help_text="The date when the license was issued. It could be that a new "
        "license is issued with the same `license_id` because it was updated. In that "
        "case, the one that has been issued last should be used."
    )
    issued_to_email = serializers.EmailField(
        help_text="Indicates to which email address the license has been issued."
    )
    issued_to_name = serializers.CharField(
        help_text="Indicates to whom the license has been issued."
    )

    class Meta:
        model = License
        fields = (
            "id",
            "license_id",
            "is_active",
            "last_check",
            "valid_from",
            "valid_through",
            "free_users_count",
            "seats_taken",
            "seats",
            "application_users_taken",
            "application_users",
            "product_code",
            "issued_on",
            "issued_to_email",
            "issued_to_name",
        )

    @lru_cache(maxsize=128)
    def get_cached_seat_usage_summary(self, obj) -> Optional[SeatUsageSummary]:
        return obj.license_type.get_seat_usage_summary(obj)

    @extend_schema_field(OpenApiTypes.INT)
    def get_seats_taken(self, obj):
        return getattr(self.get_cached_seat_usage_summary(obj), "seats_taken", None)

    @extend_schema_field(OpenApiTypes.INT)
    def get_free_users_count(self, obj):
        return getattr(
            self.get_cached_seat_usage_summary(obj), "free_users_count", None
        )

    @extend_schema_field(OpenApiTypes.INT)
    def get_application_users_taken(self, obj) -> Optional[int]:
        usage = obj.license_type.get_builder_usage_summary(obj)
        return usage.application_users_taken if usage else None


class RegisterLicenseSerializer(serializers.Serializer):
    license = serializers.CharField(help_text="The license that you want to register.")


class LicenseUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "email")


class LicenseWithUsersSerializer(LicenseSerializer):
    users = serializers.SerializerMethodField()

    class Meta(LicenseSerializer.Meta):
        fields = LicenseSerializer.Meta.fields + ("users",)

    @extend_schema_field(LicenseUserSerializer(many=True))
    def get_users(self, instance):
        users = [user.user for user in instance.users.all()]
        return LicenseUserSerializer(users, many=True).data


class LicenseUserLookupSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField(
        help_text="The name and the email address of the user."
    )

    class Meta:
        model = User
        fields = ("id", "value")

    @extend_schema_field(OpenApiTypes.STR)
    def get_value(self, instance):
        return f"{instance.first_name} ({instance.email})"
