from typing import Any, Dict, Generator, List, Tuple

from genson import SchemaBuilder
from rest_framework import serializers

from baserow.contrib.integrations.core.service_types import CoreServiceType
from baserow.core.code_runner.exceptions import (
    CodeRunnerExecutionError,
    CodeRunnerImproperlyConfigured,
    CodeRunnerResultError,
)
from baserow.core.code_runner.registries import (
    get_code_runner,
)
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.formula.validator import ensure_json
from baserow.core.registry import Instance
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import DispatchTypes
from baserow.core.services.types import DispatchResult, FormulaToResolve, ServiceDict
from baserow_enterprise.integrations.core.models import (
    CORE_CODE_SERVICE_CODE_MAX_LENGTH,
    CoreCodeService,
    CoreCodeServiceInjection,
)


class CoreCodeServiceType(CoreServiceType):
    type = "code"
    model_class = CoreCodeService
    dispatch_types = [DispatchTypes.ACTION]
    allowed_fields = ["code"]
    serializer_field_names = ["code", "injections"]
    request_serializer_field_names = ["code", "injections"]

    class SerializedDict(ServiceDict):
        code: str
        injections: List[Dict[str, str]]

    def get_schema_name(self, service: CoreCodeService) -> str:
        return f"Code{service.id}Schema"

    def generate_schema(
        self,
        service: CoreCodeService,
        allowed_fields: List[str] | None = None,
    ) -> Dict[str, Any] | None:
        if service.sample_data is None or "data" not in service.sample_data:
            return None

        schema_builder = SchemaBuilder()
        schema_builder.add_object(service.sample_data["data"])

        return {
            **schema_builder.to_schema(),
            "title": self.get_schema_name(service),
        }

    @property
    def serializer_field_overrides(self):
        from baserow_enterprise.integrations.core.api.serializers import (
            CoreCodeServiceInjectionSerializer,
        )

        return {
            "code": serializers.CharField(
                help_text=CoreCodeService._meta.get_field("code").help_text,
                allow_blank=True,
                max_length=CORE_CODE_SERVICE_CODE_MAX_LENGTH,
                required=False,
            ),
            "injections": CoreCodeServiceInjectionSerializer(
                many=True,
                required=False,
                help_text="The values to inject into the code executor context.",
            ),
        }

    @property
    def request_serializer_field_overrides(self):
        return self.serializer_field_overrides

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
        instance: CoreCodeService,
        values: Dict,
        changes: Dict[str, Tuple],
    ):
        return self.after_create(instance, values)

    def formulas_to_resolve(self, service: CoreCodeService) -> list[FormulaToResolve]:
        return [
            FormulaToResolve(
                injection.name,
                injection.formula,
                ensure_json,
                f'injection "{injection.name}"',
            )
            for injection in service.injections.all()
        ]

    def extract_properties(
        self, service: Service, path: List[str], **kwargs
    ) -> List[str]:
        if path:
            return [path[0]]
        return []

    def dispatch_data(
        self,
        service: CoreCodeService,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        try:
            return get_code_runner().run(resolved_values, service.code)
        except CodeRunnerImproperlyConfigured as exc:
            raise ServiceImproperlyConfiguredDispatchException(str(exc)) from exc
        except CodeRunnerResultError as exc:
            raise ServiceImproperlyConfiguredDispatchException(str(exc)) from exc
        except CodeRunnerExecutionError as exc:
            raise UnexpectedDispatchException(str(exc)) from exc

    def dispatch_transform(self, data: Dict[str, Any]) -> DispatchResult:
        return DispatchResult(data=data)

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
