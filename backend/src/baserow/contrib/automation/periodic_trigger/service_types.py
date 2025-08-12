from typing import Any, Dict, List, Optional

from rest_framework import serializers

from baserow.contrib.automation.periodic_trigger.models import (
    PERIODIC_INTERVAL_CHOICES,
    PeriodicTriggerService,
)
from baserow.core.services.registries import ServiceType, TriggerServiceTypeMixin
from baserow.core.services.types import ServiceDict


class PeriodicTriggerServiceType(ServiceType, TriggerServiceTypeMixin):
    type = "periodic_trigger"
    model_class = PeriodicTriggerService

    allowed_fields = [
        "interval",
        "minute",
        "hour",
        "day_of_week",
        "day_of_month",
    ]

    serializer_field_names = [
        "interval",
        "minute",
        "hour",
        "day_of_week",
        "day_of_month",
    ]

    serializer_field_overrides = {
        "interval": serializers.ChoiceField(
            choices=PERIODIC_INTERVAL_CHOICES,
            help_text=PeriodicTriggerService._meta.get_field("interval").help_text,
        ),
        "minute": serializers.IntegerField(
            min_value=0,
            max_value=59,
            required=False,
            allow_null=True,
            help_text=PeriodicTriggerService._meta.get_field("minute").help_text,
        ),
        "hour": serializers.IntegerField(
            min_value=0,
            max_value=23,
            required=False,
            allow_null=True,
            help_text=PeriodicTriggerService._meta.get_field("hour").help_text,
        ),
        "day_of_week": serializers.IntegerField(
            min_value=0,
            max_value=6,
            required=False,
            allow_null=True,
            help_text=PeriodicTriggerService._meta.get_field("day_of_week").help_text,
        ),
        "day_of_month": serializers.IntegerField(
            min_value=1,
            max_value=31,
            required=False,
            allow_null=True,
            help_text=PeriodicTriggerService._meta.get_field("day_of_month").help_text,
        ),
    }

    class SerializedDict(ServiceDict):
        interval: str
        minute: int
        hour: int
        day_of_week: int
        day_of_month: int

    def get_schema_name(self, service):
        return f"PeriodicTriggerSchema"

    def generate_schema(
        self,
        service: PeriodicTriggerService,
        allowed_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        return {
            "title": self.get_schema_name(service),
            "type": "object",
            "properties": {
                "triggered_at": {
                    "type": "string",
                    "title": "Triggered at",
                },
            },
        }
