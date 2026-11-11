from rest_framework import serializers

from baserow.contrib.dashboard.models import Dashboard

MIN_PUBLIC_PASSWORD_LENGTH = 8
MAX_PUBLIC_PASSWORD_LENGTH = 256


class HashPublicPasswordSerializerMixin:
    """
    Replaces the raw `public_password` of a dashboard request with its hash, so the
    handler, the undo/redo params and the audit log only ever see the hash. An
    empty string, or a change of `public` without a password, removes the
    password, exactly like it does for publicly shared views.
    """

    def to_internal_value(self, data):
        internal_value = super().to_internal_value(data)

        raw_public_password = internal_value.pop("public_password", None)
        if raw_public_password is not None or "public" in data:
            internal_value["public_password"] = (
                Dashboard.make_password(raw_public_password)
                if raw_public_password
                else ""  # nosec b105
            )

        return internal_value


class UpdateDashboardSharingSerializer(
    HashPublicPasswordSerializerMixin, serializers.Serializer
):
    public = serializers.BooleanField(
        required=False,
        help_text="Indicates whether the dashboard is publicly accessible to "
        "visitors. Changing it removes any previously set password.",
    )
    public_password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        min_length=MIN_PUBLIC_PASSWORD_LENGTH,
        max_length=MAX_PUBLIC_PASSWORD_LENGTH,
        help_text="The new password or an empty string to remove any previous "
        "password from the dashboard and make it publicly accessible again.",
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one of `public` or `public_password` must be provided."
            )
        return attrs
