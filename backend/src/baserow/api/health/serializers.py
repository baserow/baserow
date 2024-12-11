from rest_framework import serializers


class FullHealthCheckSerializer(serializers.Serializer):
    passing = serializers.BooleanField(
        read_only=True,
        help_text="False if any of the critical service health checks are failing, "
        "true otherwise.",
    )
    checks = serializers.DictField(
        read_only=True,
        child=serializers.CharField(),
        help_text="An object keyed by the name of the "
        "health check and the value being "
        "the result.",
    )
    celery_queue_size = serializers.IntegerField(
        help_text="The number of enqueued celery tasks."
    )
    celery_export_queue_size = serializers.IntegerField(
        help_text="The number of enqueued celery export worker tasks."
    )


class EmailTesterResponseSerializer(serializers.Serializer):
    succeeded = serializers.BooleanField(
        help_text="Whether or not the test email was sent successfully.", required=True
    )
    error_stack = serializers.CharField(
        help_text="The full stack trace and error message if the test email failed.",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    error_type = serializers.CharField(
        help_text="The type of error that occurred if the test email failed.",
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    error = serializers.CharField(
        help_text="A short message describing the error that occured if the test "
        "email failed",
        required=False,
        allow_null=True,
        allow_blank=True,
    )


class EmailTesterRequestSerializer(serializers.Serializer):
    target_email = serializers.EmailField(required=True)
