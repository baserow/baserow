from typing import Optional

from rest_framework import serializers

from baserow.api.services.serializers import PolymorphicServiceRequestSerializer


class ServiceBackedTypeMixin:
    """
    For a registry type that is always backed by one service type, like a
    workflow action or an automation node. The type names the service type it
    pins in `service_type`, and this mixin pins the `service` field of its
    request serializers to it: a payload may leave the service `type` out, and
    may not name a different one.

    Must come before `CustomFieldsInstanceMixin` in the bases.
    """

    service_type: Optional[str] = None
    """The `ServiceType.type` this type is backed by. Set by subclasses."""

    service_field_help_text = "The service which this type is associated with."

    def get_service_request_field(self) -> serializers.Field:
        return PolymorphicServiceRequestSerializer(
            default_type_name=self.service_type,
            default=None,
            required=False,
            help_text=self.service_field_help_text,
        )

    def get_serializer_class(
        self, *args, request_serializer: bool = False, extra_params=None, **kwargs
    ):
        serializer_class = super().get_serializer_class(
            *args,
            request_serializer=request_serializer,
            extra_params=extra_params,
            **kwargs,
        )

        # Only a request serializer that exposes `service` gets the pinned
        # field. Whether it does is decided by the base serializer, e.g. an
        # automation node is created without a service but updated with one,
        # and the public serializers keep their own.
        if (
            request_serializer
            and not (extra_params or {}).get("public", False)
            and "service" in serializer_class.Meta.fields
        ):
            serializer_class._declared_fields = {
                **serializer_class._declared_fields,
                "service": self.get_service_request_field(),
            }

        return serializer_class
