from django.utils.functional import lazy

from rest_framework import serializers

from baserow.core.abuse_reports.registries import abuse_report_resource_type_registry


class AbuseReportSerializer(serializers.Serializer):
    resource_type = serializers.ChoiceField(
        choices=lazy(abuse_report_resource_type_registry.get_types, list)(),
        help_text="The type of publicly shared resource that is being reported.",
    )
    identifier = serializers.CharField(
        max_length=255,
        help_text="The public identifier of the reported resource, for example the "
        "slug of a publicly shared view.",
    )
    name = serializers.CharField(
        max_length=150, help_text="The name of the person reporting the abuse."
    )
    email = serializers.EmailField(
        max_length=254,
        help_text="The email address of the person reporting the abuse.",
    )
    description = serializers.CharField(
        min_length=100,
        max_length=1000,
        help_text="A detailed description of why the resource is abusive.",
    )
    captcha_token = serializers.CharField(
        required=False,
        default="",
        allow_blank=True,
        help_text="The captcha response token, required when captcha is enabled.",
    )
