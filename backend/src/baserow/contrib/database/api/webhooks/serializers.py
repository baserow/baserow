from django.utils.functional import lazy

from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.database.api.webhooks.validators import (
    http_header_validation,
    url_validation,
)
from baserow.contrib.database.webhooks.handler import WebhookHandler
from baserow.contrib.database.webhooks.models import TableWebhook, TableWebhookCall
from baserow.contrib.database.webhooks.registries import webhook_event_type_registry
from baserow.core.utils import truncate_middle


class TableWebhookEventsSerializer(serializers.ListField):
    child = serializers.ChoiceField(
        choices=lazy(webhook_event_type_registry.get_types, list)()
    )


class TableWebhookEventConfig(serializers.Serializer):
    event_type = serializers.ChoiceField(
        help_text="The type of the event.",
        choices=webhook_event_type_registry.get_types(),
    )
    fields = serializers.ListField(
        required=False,
        child=serializers.IntegerField(),
        help_text="A list of field IDs that are related to the event.",
        allow_empty=True,
    )
    views = serializers.ListField(
        required=False,
        child=serializers.IntegerField(),
        help_text="A list of view IDs that are related to the event.",
    )


class TableWebhookCreateRequestSerializer(serializers.ModelSerializer):
    events = serializers.ListField(
        required=False,
        child=serializers.ChoiceField(choices=webhook_event_type_registry.get_types()),
        help_text="A list containing the events that will trigger this webhook.",
    )
    event_config = serializers.ListField(
        required=False,
        child=TableWebhookEventConfig(),
        help_text="A list containing the addition event options.",
    )
    headers = serializers.DictField(
        required=False,
        validators=[http_header_validation],
        help_text="The additional headers as an object where the key is the name and "
        "the value the value.",
    )
    url = serializers.CharField(
        max_length=2000,
        validators=[url_validation],
        help_text="The URL that must be called when the webhook is triggered.",
    )

    class Meta:
        model = TableWebhook
        fields = (
            "url",
            "include_all_events",
            "events",
            "event_config",
            "request_method",
            "headers",
            "name",
            "use_user_field_names",
        )


class TableWebhookUpdateRequestSerializer(serializers.ModelSerializer):
    events = serializers.ListField(
        required=False,
        child=serializers.ChoiceField(choices=webhook_event_type_registry.get_types()),
        help_text="A list containing the events that will trigger this webhook.",
    )
    event_config = serializers.ListField(
        required=False,
        child=TableWebhookEventConfig(),
        help_text="A list containing the addition event options.",
    )
    headers = serializers.DictField(
        required=False,
        validators=[http_header_validation],
        help_text="The additional headers as an object where the key is the name and "
        "the value the value.",
    )
    url = serializers.CharField(
        required=False,
        max_length=2000,
        validators=[url_validation],
        help_text="The URL that must be called when the webhook is triggered.",
    )

    class Meta:
        model = TableWebhook
        fields = (
            "url",
            "include_all_events",
            "events",
            "event_config",
            "request_method",
            "headers",
            "name",
            "active",
            "use_user_field_names",
        )
        extra_kwargs = {
            "name": {"required": False},
            "active": {"required": False},
            "use_user_field_names": {"required": False},
            "request_method": {"required": False},
        }


class TableWebhookCallSerializer(serializers.ModelSerializer):
    request = serializers.SerializerMethodField(
        help_text="A text copy of the request headers and body."
    )
    response = serializers.SerializerMethodField(
        help_text="A text copy of the response headers and body."
    )

    class Meta:
        model = TableWebhookCall
        fields = [
            "id",
            "event_id",
            "event_type",
            "called_time",
            "called_url",
            "request",
            "response",
            "response_status",
            "error",
        ]

    def get_request(self, obj):
        if obj.request is None:
            return ""
        return truncate_middle(obj.request, 100000, "\n...(truncated)\n")

    def get_response(self, obj):
        if obj.response is None:
            return ""
        return truncate_middle(obj.response, 100000, "\n...(truncated)\n")


class TableWebhookSerializer(serializers.ModelSerializer):
    events = serializers.SerializerMethodField(
        help_text="A list containing the events that will trigger this webhook.",
    )
    event_config = serializers.SerializerMethodField(
        help_text="A list containing the addition event options."
    )
    headers = serializers.SerializerMethodField(
        help_text="The additional headers as an object where the key is the name and "
        "the value the value."
    )
    calls = TableWebhookCallSerializer(
        many=True, help_text="All the calls that this webhook made."
    )

    class Meta:
        model = TableWebhook
        fields = [
            "id",
            "events",
            "event_config",
            "headers",
            "calls",
            "created_on",
            "updated_on",
            "use_user_field_names",
            "url",
            "request_method",
            "name",
            "include_all_events",
            "failed_triggers",
            "active",
        ]

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_events(self, instance):
        return [event.event_type for event in instance.events.all()]

    @extend_schema_field(TableWebhookEventConfig(many=True))
    def get_event_config(self, instance):
        events = []
        for event in instance.events.all():
            evt = {"event_type": event.event_type}
            if fields := [f.id for f in event.fields.all()]:
                evt["fields"] = fields
            if views := [v.id for v in event.views.all()]:
                evt["views"] = views
            events.append(evt)

        return [TableWebhookEventConfig(event).data for event in events]

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_headers(self, instance):
        return {header.name: header.value for header in instance.headers.all()}


class TableWebhookTestCallRequestSerializer(serializers.ModelSerializer):
    event_type = serializers.ChoiceField(
        choices=lazy(webhook_event_type_registry.get_types, list)(),
        help_text="The event type that must be used for the test call.",
    )
    headers = serializers.DictField(
        required=False,
        validators=[http_header_validation],
        help_text="The additional headers as an object where the key is the name and "
        "the value the value.",
    )
    url = serializers.CharField(
        max_length=2000,
        validators=[url_validation],
        help_text="The URL that must be called when the webhook is triggered.",
    )

    class Meta:
        model = TableWebhook
        fields = (
            "url",
            "event_type",
            "request_method",
            "headers",
            "use_user_field_names",
        )


class TableWebhookTestCallResponseSerializer(serializers.Serializer):
    request = serializers.SerializerMethodField(
        help_text="A text copy of the request headers and body."
    )
    response = serializers.SerializerMethodField(
        help_text="A text copy of the response headers and body."
    )
    status_code = serializers.SerializerMethodField(
        help_text="The HTTP response status code."
    )
    is_unreachable = serializers.SerializerMethodField(
        help_text="Indicates whether the provided URL could be reached."
    )

    @extend_schema_field(OpenApiTypes.STR)
    def get_request(self, instance):
        request = instance.get("request")

        if request is not None:
            return WebhookHandler().format_request(request)
        return ""

    @extend_schema_field(OpenApiTypes.STR)
    def get_response(self, instance):
        response = instance.get("response")
        if response is not None:
            return WebhookHandler().format_response(response)
        return ""

    @extend_schema_field(OpenApiTypes.INT)
    def get_status_code(self, instance):
        response = instance.get("response")
        if response is not None:
            return response.status_code
        return None

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_unreachable(self, instance):
        return "response" not in instance
