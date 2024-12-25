import re
from typing import Any, Dict, List, Optional, Type, Union

from django.utils.translation import gettext as _

from baserow.contrib.builder.data_providers.exceptions import (
    DataProviderChunkInvalidException,
    FormDataProviderChunkInvalidException,
)
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceDoesNotExist,
    DataSourceImproperlyConfigured,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.mixins import (
    CollectionElementTypeMixin,
    FormElementTypeMixin,
)
from baserow.contrib.builder.elements.models import FormElement
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.core.formula.exceptions import FormulaRecursion, InvalidBaserowFormula
from baserow.core.formula.registries import DataProviderType
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.user_sources.constants import DEFAULT_USER_ROLE_PREFIX
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow.core.utils import get_value_at_path
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist

RE_DEFAULT_ROLE = re.compile(rf"{DEFAULT_USER_ROLE_PREFIX}(\d+)")


class PageParameterDataProviderType(DataProviderType):
    """
    This data provider reads page parameter information from the data sent by the
    frontend during the dispatch. The data are then available for the formulas.
    """

    type = "page_parameter"

    def get_data_chunk(
        self, dispatch_context: BuilderDispatchContext, path: List[str]
    ) -> Union[int, str]:
        """
        When a page parameter is read, returns the value previously saved from the
        request object.
        """

        if len(path) != 1:
            return None

        first_part = path[0]

        return dispatch_context.request.data.get("page_parameter", {}).get(
            first_part, None
        )


class FormDataProviderType(DataProviderType):
    type = "form_data"

    def validate_data_chunk(
        self, element_id: str, data_chunk: Any, dispatch_context: DispatchContext
    ):
        """
        :param element_id: The ID of the element we're validating.
        :param data_chunk: The form data value which we're validating.
        :raises FormDataProviderChunkInvalidException: if the validation fails.
        """

        element: Type[FormElement] = ElementHandler().get_element(element_id)  # type: ignore
        element_type: FormElementTypeMixin = element.get_type()  # type: ignore

        try:
            return element_type.is_valid(element, data_chunk, dispatch_context)
        except FormDataProviderChunkInvalidException as exc:
            raise FormDataProviderChunkInvalidException(
                f"Provided value for form element with ID {element.id} of "
                f"type {element_type.type} is invalid. {str(exc)}"
            )

    def get_data_chunk(self, dispatch_context: DispatchContext, path: List[str]):
        # The path can come in two lengths:
        # - 1: The field id alone, if it's single-valued.
        # - 2a: The field id and '*', if it's multivalued.
        # - 2b: The field id and an index, if it's multivalued,
        #   but we're picking a single item.
        # Any other length is not supported and results in a None return.
        if not path or len(path) > 2:
            return None

        element_id = path[0]
        data_chunk = get_value_at_path(
            dispatch_context.request.data.get("form_data", {}), path
        )

        return self.validate_data_chunk(int(element_id), data_chunk, dispatch_context)

    def import_path(self, path, id_mapping, **kwargs):
        """
        Update the form element id of the path.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :return: The updated path.
        """

        form_element_id, *rest = path

        if "builder_page_elements" in id_mapping:
            form_element_id = id_mapping["builder_page_elements"].get(
                int(form_element_id), form_element_id
            )

        return [str(form_element_id), *rest]


class DataSourceDataProviderType(DataProviderType):
    """
    The data source provider can read data from registered page data sources.
    """

    type = "data_source"

    def get_data_chunk(self, dispatch_context: BuilderDispatchContext, path: List[str]):
        """Load a data chunk from a datasource of the page in context."""

        data_source_id, *rest = path

        data_source = DataSourceHandler().get_data_source_with_cache(
            dispatch_context.page, int(data_source_id)
        )

        # Declare the call and check for recursion
        try:
            dispatch_context.add_call(data_source.id)
        except FormulaRecursion:
            raise DataSourceImproperlyConfigured("Recursion detected.")

        dispatch_result = DataSourceHandler().dispatch_data_source(
            data_source, dispatch_context
        )

        if data_source.service.get_type().returns_list:
            dispatch_result = dispatch_result["results"]

        return get_value_at_path(dispatch_result, rest)

    def import_path(self, path, id_mapping, **kwargs):
        """
        Update the data_source_id of the path and also apply the data_source type
        update when importing a path.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :return: The updated path.
        """

        data_source_id, *rest = path

        if "builder_data_sources" in id_mapping:
            try:
                data_source_id = id_mapping["builder_data_sources"][int(data_source_id)]
                data_source = DataSourceHandler().get_data_source(data_source_id)
            except (KeyError, DataSourceDoesNotExist):
                # The data source have probably been deleted so we return the
                # initial path
                return [str(data_source_id), *rest]

            service_type = data_source.service.specific.get_type()
            rest = service_type.import_path(rest, id_mapping)

        return [str(data_source_id), *rest]

    def extract_properties(self, path: List[str], **kwargs) -> Dict[str, List[str]]:
        """
        Given a list of formula path parts, call the ServiceType's
        extract_properties() method and return a dict where the keys are the
        Service IDs and the values are the field names.

        E.g. given that path is: ['96', '1', 'field_5191'], returns
        {1: ['field_5191']}.
        """

        if not path:
            return {}

        _data_source_id, *rest = path
        try:
            data_source_id = int(_data_source_id)
        except ValueError:
            return {}

        try:
            data_source = DataSourceHandler().get_data_source(data_source_id)
        except DataSourceDoesNotExist as exc:
            # The data source has probably been deleted
            raise InvalidBaserowFormula() from exc

        service_type = data_source.service.specific.get_type()
        return {data_source.service_id: service_type.extract_properties(rest, **kwargs)}


class DataSourceContextDataProviderType(DataProviderType):
    """
    The data source context provider provides extra metadata related to the data source.
    """

    type = "data_source_context"

    def get_data_chunk(self, dispatch_context: BuilderDispatchContext, path: List[str]):
        """Load a data chunk from a datasource of the page in context."""

        data_source_id, *rest = path
        data_source = DataSourceHandler().get_data_source_with_cache(
            dispatch_context.page, int(data_source_id)
        )

        service_type = data_source.service.get_type()
        context_data = service_type.get_context_data(data_source.service)

        return get_value_at_path(context_data, rest)

    def import_path(self, path: List[str], id_mapping: Dict, **kwargs):
        """
        Update the data_source_id of the path, similar to
        `DataSourceDataProviderType.import_path.`
        """

        data_source_id, *rest = path

        if "builder_data_sources" in id_mapping:
            try:
                data_source_id = id_mapping["builder_data_sources"][int(data_source_id)]
                data_source = DataSourceHandler().get_data_source(data_source_id)
            except (KeyError, DataSourceDoesNotExist):
                # The data source have probably been deleted, so we return the
                # initial path
                return [str(data_source_id), *rest]

            service_type = data_source.service.specific.get_type()
            rest = service_type.import_context_path(rest, id_mapping)

        return [str(data_source_id), *rest]

    def extract_properties(self, path: List[str], **kwargs) -> Dict[str, List[str]]:
        """
        Given a list of formula path parts, call the ServiceType's
        extract_properties() method and return a dict where the keys are the
        Service IDs and the values are the field names.

        E.g. given that path is: ['96', '1', 'field_5191'], returns
        {1: ['field_5191']}.
        """

        if not path:
            return {}

        _data_source_id, *rest = path
        try:
            data_source_id = int(_data_source_id)
        except ValueError:
            return {}

        try:
            data_source = DataSourceHandler().get_data_source(data_source_id)
        except DataSourceDoesNotExist as exc:
            # The data source has probably been deleted
            raise InvalidBaserowFormula() from exc

        service_type = data_source.service.specific.get_type()
        return {data_source.service_id: service_type.extract_properties(rest, **kwargs)}


class CurrentRecordDataProviderType(DataProviderType):
    """
    The frontend data provider to get the current row content
    """

    type = "current_record"

    def get_data_chunk(self, dispatch_context: BuilderDispatchContext, path: List[str]):
        """
        Get the current record data from the request data.

        :param dispatch_context: The dispatch context.
        :param path: The path to the data.
        :return: The data at the path.
        """

        try:
            current_record = dispatch_context.request.data["current_record"]
        except KeyError:
            return None

        # If we want the current record index, and nothing else, then
        # return the `current_record` from the dispatch context. The
        # index isn't a value that can be returned by the data source
        # provider's `get_data_chunk`.
        if len(path) == 1 and path[0] == "__idx__":
            return current_record

        first_collection_element_ancestor = ElementHandler().get_first_ancestor_of_type(
            dispatch_context.workflow_action.element_id,
            CollectionElementTypeMixin,
        )
        data_source_id = first_collection_element_ancestor.specific.data_source_id

        # Narrow down our range to just our record index.
        dispatch_context = dispatch_context.from_context(
            dispatch_context,
            offset=current_record,
            count=1,
        )

        return DataSourceDataProviderType().get_data_chunk(
            dispatch_context, [data_source_id, "0", *path]
        )

    def import_path(self, path, id_mapping, data_source_id=None, **kwargs):
        """
        Applies the updates of the related data_source.

        :param path: the path part list.
        :param id_mapping: The id_mapping of the process import.
        :param data_source_id: The id of the data_source related to this data provider.
        :return: The updated path.
        """

        # We don't need to import the row index (__idx__)
        if len(path) == 1 and path[0] == "__idx__":
            return path

        if not data_source_id:
            return path

        data_source = DataSourceHandler().get_data_source(data_source_id)
        service_type = data_source.service.specific.get_type()
        # Here we add a fake row part to make it match the usual shape for this path
        _, *rest = service_type.import_path([0, *path], id_mapping)

        return rest

    def extract_properties(
        self,
        path: List[str],
        data_source_id: Optional[int] = None,
        schema_property: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, List[str]]:
        """
        Given a list of formula path parts, call the ServiceType's
        extract_properties() method and return a dict where the keys are the
        Service IDs and the values are the field names.

        E.g. given that path is: ['96', '1', 'field_5191'], returns
        {1: ['field_5191']}.
        """

        if not path:
            return {}

        if data_source_id is None:
            return {}

        try:
            data_source = DataSourceHandler().get_data_source(data_source_id)
        except DataSourceDoesNotExist as exc:
            # The data source is probably not accessible so we raise an invalid formula
            raise InvalidBaserowFormula() from exc

        service_type = data_source.service.specific.get_type()

        if service_type.returns_list:
            # Here we add a fake row part to make it match the usual shape
            # for this path
            if schema_property:
                path = ["0", schema_property, *path]
            else:
                path = ["0", *path]
        else:
            # Current Record could also use Get Row service type (via Repeat
            # element), so we need to add the field name if it is available.
            if not schema_property:
                return {}
            else:
                path = [schema_property, *path]

        return {data_source.service_id: service_type.extract_properties(path, **kwargs)}


class PreviousActionProviderType(DataProviderType):
    """
    The previous action provider can read data from registered page workflow actions.
    """

    type = "previous_action"

    def get_data_chunk(self, dispatch_context: DispatchContext, path: List[str]):
        previous_action_id, *rest = path
        previous_action = dispatch_context.request.data.get("previous_action", {})

        if previous_action_id not in previous_action:
            message = "The previous action id is not present in the dispatch context"
            raise DataProviderChunkInvalidException(message)
        return get_value_at_path(previous_action, path)

    def import_path(self, path, id_mapping, **kwargs):
        workflow_action_id, *rest = path

        if "builder_workflow_actions" in id_mapping:
            try:
                workflow_action_id = id_mapping["builder_workflow_actions"][
                    int(workflow_action_id)
                ]
                workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
                    workflow_action_id
                )
            except (KeyError, WorkflowActionDoesNotExist):
                return [str(workflow_action_id), *rest]

            service_type = workflow_action.service.specific.get_type()
            rest = service_type.import_path(rest, id_mapping)

        return [str(workflow_action_id), *rest]


class UserDataProviderType(DataProviderType):
    """
    This data provider user the user in `request.user_source_user` to resolve formula
    paths. This property is injected into the request by the
    `baserow.api.user_sources.middleware.AddUserSourceUserMiddleware` django middleware.
    """

    type = "user"

    def translate_default_user_role(self, user: UserSourceUser) -> str:
        """
        Returns the translated version of the user role if it is a default role,
        otherwise returns the same user_role back without any changes.
        """

        matches = RE_DEFAULT_ROLE.search(user.role)
        if not matches:
            return user.role

        return _("%(user_source_name)s member") % {
            "user_source_name": user.user_source.name
        }

    def get_data_chunk(self, dispatch_context: DispatchContext, path: List[str]):
        """
        Loads the user_source_user from the request object and expose it to the
        formulas.
        """

        user = dispatch_context.request.user_source_user

        is_authenticated = user.is_authenticated

        if is_authenticated:
            user = {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": self.translate_default_user_role(user),
            }
        else:
            user = {"id": 0, "username": "", "email": "", "role": ""}

        return get_value_at_path({"is_authenticated": is_authenticated, **user}, path)
