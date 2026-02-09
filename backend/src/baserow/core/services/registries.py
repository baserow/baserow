from abc import ABC, abstractmethod
from dataclasses import fields
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

from loguru import logger
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.formula import resolve_formula
from baserow.core.formula.exceptions import (
    InvalidFormulaContext,
    InvalidFormulaContextContent,
)
from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.registry import (
    APIUrlsInstanceMixin,
    APIUrlsRegistryMixin,
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    InstanceWithFormulaMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    PublicCustomFieldsInstanceMixin,
    Registry,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.types import DispatchResult, FormulaToResolve

from .exceptions import (
    DispatchException,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    ServiceTypeDoesNotExist,
    TriggerServiceNotDispatchable,
    UnexpectedDispatchException,
)
from .models import Service
from .types import ServiceDictSubClass, ServiceSubClass


class DispatchTypes(str, Enum):
    # A `ServiceType` which performs an action.
    ACTION = "action"
    # A `ServiceType` which fetches data.
    DATA = "data"
    # A `ServiceType` which responds to events.
    EVENT = "event"


class ServiceType(
    APIUrlsInstanceMixin,
    InstanceWithFormulaMixin,
    EasyImportExportMixin[ServiceSubClass],
    ModelInstanceMixin[ServiceSubClass],
    PublicCustomFieldsInstanceMixin,
    CustomFieldsInstanceMixin,
    Instance,
    ABC,
):
    """
    A service type describe a specific service of an external integration.
    """

    integration_type = None

    SerializedDict: Type[ServiceDictSubClass]
    parent_property_name = "integration"
    id_mapping_name = "services"

    default_serializer_field_names = ["sample_data"]

    # Does this service return a list of record?
    returns_list = False

    # What parent object is responsible for dispatching this `ServiceType`?
    # It could be via a `DataSource`, in which case `DATA` should be
    # chosen, or via a `WorkflowAction`, in which case `ACTION`
    # should be chosen. Multiple dispatch types can be selected if the service is
    # used across modules.
    dispatch_types: List[DispatchTypes] = []

    # By default all service data should be hidden
    public_serializer_field_names = []
    public_serializer_field_overrides = {}

    def can_be_dispatched_as(self, dispatch_type: DispatchTypes) -> bool:
        """
        Returns whether this service can be dispatched as the given dispatch type.

        :param dispatch_type: The dispatch type to check.
        :return: If the service can be dispatched as the given type.
        """

        return dispatch_type in self.dispatch_types

    def get_integration_type(self):
        from baserow.core.integrations.registries import integration_type_registry

        if self.integration_type:
            return integration_type_registry.get(self.integration_type)

        return None

    def get_id_property(self, service: Service) -> str:
        """
        Returns the property name that contains the unique `ID` of a row for this
        service.

        :param service: the instance of the service.
        :return: a string identifying the ID property name.
        """

        # Sane default
        return "id"

    def get_name_property(self, service: Service) -> Optional[str]:
        """
        We need the name of the records for some elements (like the record selector).
        This method returns it depending on the service.

        :param service: the instance of the service.
        :return: a string identifying the name property name.
        """

        return None

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[ServiceSubClass] = None,
    ) -> Dict[str, Any]:
        """
        The prepare_values hook gives the possibility to change the provided values
        that just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object. It's also an opportunity to add
        specific validations.

        :param values: The provided values.
        :param user: The user on whose behalf the change is made.
        :param instance: The current instance if it exists.
        :return: The updated values.
        """

        # We load the actual integration object
        if "integration_id" in values:
            integration_id = values.pop("integration_id")
            if integration_id is not None:
                try:
                    integration = IntegrationHandler().get_integration(integration_id)
                except IntegrationDoesNotExist:
                    raise DRFValidationError(
                        f"The integration with ID {integration_id} does not exist."
                    )

                if instance and instance.integration_id:
                    # `integration` cannot belong to a different application
                    # than the one that `instance.integration` points to.
                    current_integration_id = instance.integration.application_id
                    if integration.application_id != current_integration_id:
                        raise DRFValidationError(
                            detail=f"The integration with ID {integration_id} is not "
                            f"related to the given application {current_integration_id}.",
                            code="invalid_integration",
                        )

                values["integration"] = integration
            else:
                values["integration"] = None

        return values

    def export_prepared_values(self, instance: Service):
        """
        Returns a serializable dict of prepared values for the service attributes.
        This method is the counterpart of `prepare_values`. It is called
        by undo/redo ActionHandler to store the values in a way that could be
        restored later.

        :param instance: The service instance to export values for.
        :return: A dict of prepared values.
        """

        values = {key: getattr(instance, key) for key in self.allowed_fields}
        return values

    def after_create(self, instance: ServiceSubClass, values: Dict):
        """
        This hook is called right after the service has been created.

        :param instance: The created service instance.
        :param values: The values that were passed when creating the service
            metadata.
        """

    def after_update(
        self,
        instance: ServiceSubClass,
        values: Dict,
        changes: Dict[str, Tuple],
    ):
        """
        This hook is called right after the service has been updated.

        :param instance: The updated service instance.
        :param values: The values that were passed when creating the service
            metadata.
        :param changes: A dictionary containing all changes which were made to the
            service prior to `after_update` being called.
        """

    def before_delete(self, instance: ServiceSubClass):
        """
        This hook is called just before the service will be deleted.

        :param instance: The to be deleted service instance.
        """

    def get_context_data(self, service: ServiceSubClass):
        """
        Return the context data for this service.

        This can be overridden by child classes to provide extra context data,
        to complement this service results.
        """

        return None

    def get_sample_data(
        self, service: ServiceSubClass, dispatch_context: DispatchContext
    ) -> Optional[Dict[Any, Any]]:
        """Return the sample data for this service."""

        return service.sample_data

    def get_context_data_schema(self, service: ServiceSubClass):
        """Return the schema for the context data."""

        return None

    def formulas_to_resolve(self, service: ServiceSubClass) -> list[FormulaToResolve]:
        return []

    def _get_validation_details(self, error):
        detail = error.detail

        if isinstance(detail, str):
            return detail
        elif isinstance(detail, list):
            return str(detail[0]) if detail else ""
        elif isinstance(detail, dict):
            for field, errors in detail.items():
                if isinstance(errors, list) and errors:
                    return str(errors[0])
                else:
                    return str(errors)
        return str(detail)

    def resolve_service_formulas(
        self,
        service: ServiceSubClass,
        dispatch_context: DispatchContext,
    ) -> Dict[str, Any]:
        """
        Responsible for resolving any formulas in the service's fields, and then
        performing a validation step prior to `ServiceType.dispatch_data` is executed.

        :param service: The service instance we want to use.
        :param dispatch_context: The runtime_formula_context instance used to
            resolve formulas (if any).
        :return: Any
        """

        resolved_values = {}
        for key, formula_ctx, ensurer, label in self.formulas_to_resolve(service):
            try:
                resolved_values[key] = ensurer(
                    resolve_formula(
                        formula_ctx,
                        formula_runtime_function_registry,
                        dispatch_context.clone(),
                    )
                )
            except InvalidFormulaContext as e:
                raise InvalidContextDispatchException(str(e)) from e
            except InvalidFormulaContextContent as e:
                message = f"Value error for {label}: {str(e)}"
                raise InvalidContextContentDispatchException(message) from e
            except ValidationError as e:
                message = f"Value error for {label}: {e.message}"
                raise InvalidContextContentDispatchException(message) from e
            except BaserowFormulaException as e:
                message = f"Error in formula for {label}: {str(e)}"
                raise ServiceImproperlyConfiguredDispatchException(message) from e
            except DispatchException:
                raise
            except Exception as e:
                logger.exception(f"Unexpected error for {label}")
                message = f"Unknown error in formula for {label}: {str(e)}"
                raise UnexpectedDispatchException(message) from e

        return resolved_values

    def prepare_value_path(self, service: Service, path: List[str]):
        """
        Allow to change the path inside a service before it's used.
        """

        return path

    def dispatch_transform(
        self,
        data: Any,
    ) -> DispatchResult:
        """
        Responsible for taking the `dispatch_data` result and transforming its value
        for API consumer's consumption.

        :param data: The `dispatch_data` result.
        :return: The transformed `dispatch_transform` result.
        """

    def dispatch_data(
        self,
        service: ServiceSubClass,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ) -> Any:
        """
        Responsible for executing the service's principle task.

        :param service: The service instance to dispatch with.
        :param resolved_values: If the service has any formulas, this dictionary will
            contain their resolved values.
        :param dispatch_context: The context used for the dispatch.
        :return: The service `dispatch_data` result if any.
        """

    def dispatch(
        self,
        service: ServiceSubClass,
        dispatch_context: DispatchContext,
    ) -> DispatchResult:
        """
        Responsible for calling `dispatch_data` and `dispatch_transform` to execute
        the service's task, and generating the dispatch's response, respectively.

        :param service: The service instance to dispatch with.
        :param dispatch_context: The context used for the dispatch.
        :return: The service dispatch result if any.
        """

        # If simulated, try to return existing sample data
        if (
            dispatch_context.use_sample_data
            and (
                dispatch_context.update_sample_data_for is None
                or service not in dispatch_context.update_sample_data_for
            )
            and (sample_data := self.get_sample_data(service, dispatch_context))
            is not None
        ):
            return DispatchResult(**sample_data)

        try:
            resolved_values = self.resolve_service_formulas(service, dispatch_context)
            data = self.dispatch_data(service, resolved_values, dispatch_context)
            serialized_data = self.dispatch_transform(data)
        except Exception as e:
            if dispatch_context.use_sample_data and (
                dispatch_context.update_sample_data_for is None
                or service in dispatch_context.update_sample_data_for
            ):
                service.sample_data = {"_error": str(e)}
                service.save()
            raise
        else:
            if dispatch_context.use_sample_data and (
                dispatch_context.update_sample_data_for is None
                or service in dispatch_context.update_sample_data_for
            ):
                sample_data = {}
                for field in fields(serialized_data):
                    value = getattr(serialized_data, field.name)
                    sample_data[field.name] = value

                service.sample_data = sample_data
                service.save()
            return serialized_data

    def remove_unused_field_names(
        self,
        row: Dict[str, Any],
        field_names: List[str],
    ) -> Dict[str, Any]:
        """
        Given a row dictionary, return a version of it that only contains keys
        existing in the field_names list.
        """

        return {key: value for key, value in row.items() if key in field_names}

    def sanitize_result(self, service, result, allowed_field_names):
        """
        Remove the non public fields from the result.
        """

        if self.returns_list:
            return {
                **result,
                "results": [
                    self.remove_unused_field_names(row, allowed_field_names)
                    for row in result["results"]
                ],
            }
        else:
            return self.remove_unused_field_names(result, allowed_field_names)

    def get_schema_name(self, service: Service) -> str:
        """
        The default schema name added to the `title` in a JSON Schema object.

        :param service: The service we want to generate a schema `title` with.
        :return: A string.
        """

        return f"Service{service.id}Schema"

    def generate_schema(
        self, service: Service, allowed_fields: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Responsible for generating the full JSON Schema response. Must be
        overridden by child classes so that the can return their service's
        schema.

        :param service: The service we want to generate a schema for.
        :param allowed_fields: A list of fields that are allowed to be included in the
            schema.
        :return: None, or a dictionary representing the schema.
        """

        return None

    def enhance_queryset(self, queryset):
        """
        Allow to enhance the queryset when querying the service mainly to improve
        performances.
        """

        return queryset

    def import_path(self, path, id_mapping, **kwargs):
        """
        Allows to hook into the path import resolution.

        If not implemented, returns the path as it is.
        """

        return path

    def import_context_path(
        self, path: List[str], id_mapping: Dict[int, int], **kwargs
    ):
        """
        Allows to hook into the context path import resolution.

        If not implemented, returns the path as it is.
        """

        return path

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        import_formula: Callable[[str, Dict[str, Any]], str] = None,
        **kwargs,
    ):
        created_instance = super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            import_formula=import_formula,
            **kwargs,
        )

        if import_formula is not None:
            updated_models = self.import_formulas(
                created_instance, id_mapping, import_formula, **kwargs
            )

            [m.save() for m in updated_models]

        return created_instance

    def extract_properties(self, path: List[str], **kwargs) -> List[str]:
        return []

    def import_property_name(
        self, property_name: str, id_mapping: Dict[str, Any]
    ) -> Optional[str]:
        """
        Allows to hook into the property name import resolution.

        If not implemented, returns the property name as it is.
        """

        return property_name

    def get_edges(self, service):
        return {"": {"label": ""}}


ServiceTypeSubClass = TypeVar("ServiceTypeSubClass", bound=ServiceType)


class ListServiceTypeMixin:
    """A mixin for services that return lists."""

    returns_list = True

    @abstractmethod
    def get_record_names(
        self,
        service: Service,
        record_ids: List[int],
        dispatch_context: DispatchContext,
    ) -> Dict[str, str]:
        """
        Return the record name associated with each one of the provided record ids.

        Implementation is required for any service that uses this mixin.

        :param service: The available service to use.
        :param record_ids: The list containing the record identifiers.
        :param dispatch_context: The context used for the dispatch.
        :return: A dictionary mapping each record to its name.
        """

    @abstractmethod
    def get_max_result_limit(self, service: Service):
        """
        The maximum number of records this service is able to return.
        Is the maximum is `None`, then it's unlimited.
        """

    @abstractmethod
    def get_default_result_limit(self, service: Service):
        """
        The default number of records this service will return,
        unless instructed otherwise by a user.
        """


class TriggerServiceTypeMixin(ABC):
    # The callable function which should be called when the event occurs.
    on_event: Callable = lambda *args: None

    # The service is always dispatched by an event.
    dispatch_types = [DispatchTypes.EVENT]

    def can_immediately_be_tested(self, service: Service):
        """
        Does this trigger can be dispatched immediately. It's possible only if the
        trigger data can be generated
        """

        return False

    def dispatch_data(
        self,
        service: Service,
        resolved_values: Dict[str, Any],
        dispatch_context: DispatchContext,
    ):
        # By default a trigger uses the data from the dispatch context event_payload
        if dispatch_context.event_payload is not None:
            return dispatch_context.event_payload

        raise TriggerServiceNotDispatchable()

    def dispatch_transform(self, data):
        return DispatchResult(data=data)

    def start_listening(self, on_event: Callable) -> None:
        """
        Triggers, a type of service which respond to internal and external events and
        trigger their own dispatch, need the ability to "start" listening to their
        events. This method ensure that we only begin listening when we need to.

        :param on_event: A callable function which should be called when
            the internal or external event occurs.
        """

        self.on_event = on_event

    def stop_listening(self) -> None:
        """
        Triggers, a type of service which respond to internal and external events and
        trigger their own dispatch, need the ability to "stop" listening to their
        events. This method ensure that we can stop listening when we need to.
        :return:
        """


class ServiceTypeRegistry(
    APIUrlsRegistryMixin,
    ModelRegistryMixin[ServiceSubClass, ServiceTypeSubClass],
    Registry[ServiceTypeSubClass],
    CustomFieldsRegistryMixin,
):
    """
    Contains the registered service types.
    """

    name = "integration_service"
    does_not_exist_exception_class = ServiceTypeDoesNotExist


service_type_registry: ServiceTypeRegistry = ServiceTypeRegistry()
