from typing import Dict, Generator, List, Tuple

from rest_framework import serializers

from baserow.contrib.integrations.core.service_types import CoreServiceType
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.registry import Instance
from baserow.core.services.models import Service
from baserow.core.services.registries import DispatchTypes
from baserow.core.services.types import ServiceDict
from baserow_enterprise.integrations.core.models import (
    CoreCodeService,
    CoreCodeServiceInjection,
)


class CoreCodeServiceType(CoreServiceType):
    type = "code"
    model_class = CoreCodeService
    dispatch_types = [DispatchTypes.ACTION]
    allowed_fields = ["code"]
    serializer_field_names = ["code", "injections"]

    class SerializedDict(ServiceDict):
        code: str
        injections: List[Dict[str, str]]

    @property
    def serializer_field_overrides(self):
        from baserow_enterprise.integrations.core.api.serializers import (
            CoreCodeServiceInjectionSerializer,
        )

        return {
            "code": serializers.CharField(
                help_text=CoreCodeService._meta.get_field("code").help_text,
                allow_blank=True,
                required=False,
            ),
            "injections": CoreCodeServiceInjectionSerializer(
                many=True,
                required=False,
                help_text="The values to inject into the code executor context.",
            ),
        }

    def after_create(
        self,
        instance: CoreCodeService,
        values: Dict,
    ):
        if "injections" in values:
            instance.injections.all().delete()
            CoreCodeServiceInjection.objects.bulk_create(
                [
                    CoreCodeServiceInjection(
                        service=instance,
                        name=injection["name"],
                        formula=injection["formula"],
                    )
                    for injection in values["injections"]
                ]
            )

    def after_update(
        self,
        instance,
        values,
        changes: Dict[str, Tuple],
    ):
        return self.after_create(instance, values)

    def formula_generator(
        self, service: Service
    ) -> Generator[str | Instance, str, None]:
        yield from super().formula_generator(service)

        for injection in service.injections.all():
            new_formula = yield BaserowFormulaObject.to_formula(injection.formula)
            if new_formula is not None:
                injection.formula = new_formula
                yield injection

    def serialize_property(
        self,
        service: CoreCodeService,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "injections":
            return [
                {
                    "name": injection.name,
                    "formula": injection.formula,
                }
                for injection in service.injections.all()
            ]

        return super().serialize_property(
            service, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def create_instance_from_serialized(
        self,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        injections = serialized_values.pop("injections", [])

        service = super().create_instance_from_serialized(
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        CoreCodeServiceInjection.objects.bulk_create(
            [
                CoreCodeServiceInjection(
                    **injection,
                    service=service,
                )
                for injection in injections
            ]
        )

        return service

    def enhance_queryset(self, queryset):
        return super().enhance_queryset(queryset).prefetch_related("injections")
