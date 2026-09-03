from typing import Dict, List

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.exceptions import ThrottledAPIException
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.api.rows.errors import ERROR_ROW_DOES_NOT_EXIST
from baserow.contrib.database.api.workflow_actions.errors import (
    ERROR_WORKFLOW_ACTION_DISPATCH_FAILED,
    ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS,
    ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
    ERROR_WORKFLOW_ACTION_NOT_IN_FIELD,
)
from baserow.contrib.database.api.workflow_actions.serializers import (
    CreateDatabaseWorkflowActionSerializer,
    DatabaseWorkflowActionSerializer,
    DispatchedClientActionSerializer,
    DispatchWorkflowActionsResponseSerializer,
    DispatchWorkflowActionsSerializer,
    OrderWorkflowActionsSerializer,
    UpdateDatabaseWorkflowActionSerializer,
)
from baserow.contrib.database.api.workflow_actions.throttling import (
    ButtonFieldDispatchUserRateThrottle,
    ButtonFieldDispatchWorkspaceRateThrottle,
)
from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
    WorkflowActionNotInField,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.feature_flags import FF_BUTTON_FIELD, feature_flag_is_enabled
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist


class DatabaseWorkflowActionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a workflow action for the button field related "
                "to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="create_database_field_workflow_action",
        description="Creates a new database workflow action.",
        request=DiscriminatorCustomFieldsMappingSerializer(
            database_workflow_action_type_registry,
            CreateDatabaseWorkflowActionSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                database_workflow_action_type_registry,
                DatabaseWorkflowActionSerializer,
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body_custom_fields(
        database_workflow_action_type_registry,
        base_serializer_class=CreateDatabaseWorkflowActionSerializer,
        serializer_class_context={"application_type": DatabaseApplicationType},
    )
    def post(self, request, data: Dict, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        type_name = data.pop("type")
        workflow_action_type = database_workflow_action_type_registry.get(type_name)
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_action = DatabaseWorkflowActionService().create_workflow_action(
            request.user, workflow_action_type, field, **data
        )

        serializer = database_workflow_action_type_registry.get_serializer(
            workflow_action,
            DatabaseWorkflowActionSerializer,
            context={"user": request.user},
        )

        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the workflow actions of the button field "
                "related to the provided Id.",
            )
        ],
        tags=["Database table fields"],
        operation_id="list_database_field_workflow_actions",
        description=(
            "Lists all the workflow actions of the button field related to the "
            "provided parameter if the user has access to the related "
            "database's workspace."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                database_workflow_action_type_registry,
                DatabaseWorkflowActionSerializer,
                many=True,
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_actions = DatabaseWorkflowActionService().get_workflow_actions(
            request.user, field
        )

        data = [
            database_workflow_action_type_registry.get_serializer(
                workflow_action,
                DatabaseWorkflowActionSerializer,
                context={"user": request.user},
            ).data
            for workflow_action in workflow_actions
        ]

        return Response(data)


class DatabaseWorkflowActionView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_action_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow action.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="delete_database_field_workflow_action",
        description="Deletes the workflow action related by the given id.",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkflowActionDoesNotExist: ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, workflow_action_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        workflow_action = DatabaseWorkflowActionHandler().get_workflow_action(
            workflow_action_id
        )

        DatabaseWorkflowActionService().delete_workflow_action(
            request.user, workflow_action
        )

        return Response(status=204)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_action_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow action.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="update_database_field_workflow_action",
        description="Updates an existing database workflow action.",
        request=CustomFieldRegistryMappingSerializer(
            database_workflow_action_type_registry,
            UpdateDatabaseWorkflowActionSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                database_workflow_action_type_registry,
                DatabaseWorkflowActionSerializer,
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(
                [
                    "ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkflowActionDoesNotExist: ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, workflow_action_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        # Locked for the request: a type change swaps the action's own row, so
        # a concurrent update must not read it half way through.
        workflow_action = (
            DatabaseWorkflowActionHandler().get_workflow_action_for_update(
                workflow_action_id
            )
        )
        workflow_action_type = type_from_data_or_registry(
            request.data, database_workflow_action_type_registry, workflow_action
        )
        data = validate_data_custom_fields(
            workflow_action_type.type,
            database_workflow_action_type_registry,
            request.data,
            base_serializer_class=UpdateDatabaseWorkflowActionSerializer,
            serializer_class_context={"application_type": DatabaseApplicationType},
            partial=True,
        )

        workflow_action_updated = (
            DatabaseWorkflowActionService().update_workflow_action(
                request.user, workflow_action, **data
            )
        )

        serializer = database_workflow_action_type_registry.get_serializer(
            workflow_action_updated,
            DatabaseWorkflowActionSerializer,
            context={"user": request.user},
        )
        return Response(serializer.data)


class OrderDatabaseWorkflowActionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The button field the workflow actions belong to.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="order_database_field_workflow_actions",
        description="Apply a new order to the workflow actions of a button field.",
        request=OrderWorkflowActionsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKFLOW_ACTION_NOT_IN_FIELD",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkflowActionNotInField: ERROR_WORKFLOW_ACTION_NOT_IN_FIELD,
        }
    )
    @validate_body(OrderWorkflowActionsSerializer)
    def post(self, request, data: Dict, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        DatabaseWorkflowActionService().order_workflow_actions(
            request.user, field, data["workflow_action_ids"]
        )

        return Response(status=204)


class DispatchDatabaseWorkflowActionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def _reserve_dispatch_budget(
        self, request, field: ButtonField, workflow_actions: list
    ) -> List[list]:
        """
        Takes a slot from each rate limit guarding external clicks, one per
        action that will reach outside Baserow. Per action rather than per
        click, or a button carrying ten requests would send ten for the price
        of one.

        Reserved up front, the only way a limit holds under a burst, and given
        back afterwards for whatever the click did not spend. A limit that
        denies mid way gives back what came before it.

        Nothing is reserved for a button that only touches rows here.

        :param request: The click.
        :param field: The button field being clicked.
        :param workflow_actions: The snapshot the click will run.
        :return: One list of throttles per external action, each holding a
            slot.
        :raises ThrottledAPIException: When the click is over a limit, or
            carries more external actions than one could ever hold.
        """

        external_count = sum(
            1
            for workflow_action in workflow_actions
            if workflow_action.get_type().is_external
        )
        if not external_count:
            return []

        workspace_id = field.table.database.workspace_id
        reservations: List[list] = []

        try:
            for build_throttle in (
                ButtonFieldDispatchUserRateThrottle,
                lambda: ButtonFieldDispatchWorkspaceRateThrottle(workspace_id),
            ):
                held: list = []
                reservations.append(held)
                for _ in range(
                    self._slots_to_take(build_throttle(), request, external_count)
                ):
                    throttle = build_throttle()
                    throttle.allow_request(request, self)
                    held.append(throttle)
        except ThrottledAPIException:
            self._release_dispatch_budget(reservations)
            raise

        return reservations

    def _slots_to_take(self, throttle, request, external_count: int) -> int:
        """
        How many slots one click takes from a limit: one for every action of
        it that reaches outside Baserow.

        A button carrying more of them than the limit could ever hold is
        refused instead. Capping the reservation would be worse than counting
        it wrong: the click would still send every one of its requests, so the
        limit would be paying for a burst of any size it likes, which is the
        one thing it exists to stop. Such a button cannot be clicked inside
        the budget at all, and waiting does not change that, so the answer
        says so rather than pretending the next window will help.

        :param throttle: The limit being asked.
        :param request: The click.
        :param external_count: How many actions of it reach outside Baserow.
        :raises ThrottledAPIException: When the button carries more external
            actions than the limit could ever hold.
        :return: The number of slots to reserve.
        """

        rate_limits = tuple(throttle.get_rate_limits(request) or ())

        if not rate_limits or throttle.get_cache_key(request) is None:
            # Switched off, or the caller is exempt, so `allow_request` is a
            # no-op and one is enough to keep the bookkeeping the same shape.
            return 1

        capacity = min(rate.number_of_calls for rate in rate_limits)

        if external_count > capacity:
            raise ThrottledAPIException(
                detail=(
                    f"This button sends {external_count} requests outside "
                    f"Baserow, and this installation allows at most "
                    f"{capacity}. Waiting will not help: it has to carry "
                    f"fewer of them."
                )
            )

        return external_count

    def _release_dispatch_budget(self, reservations: List[list], keep: int = 0) -> None:
        """
        Gives back the slots the click did not spend.

        :param reservations: What `_reserve_dispatch_budget` took, one list per
            limit.
        :param keep: How many external actions the click really ran. Their
            slots stay spent, a failed request included: the budget caps the
            traffic, not the successes. A limit that gave fewer slots than that
            keeps all of them.
        """

        for held in reservations:
            for throttle in held[min(keep, len(held)) :]:
                throttle.release()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Runs the button field's actions, in order, for the "
                "provided row.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="dispatch_database_field_workflow_actions",
        description=(
            "Runs every workflow action of a button field, in order, for the "
            "given row, and returns one result per action."
        ),
        request=DispatchWorkflowActionsSerializer,
        responses={
            200: DispatchWorkflowActionsResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(
                [
                    "ERROR_FIELD_DOES_NOT_EXIST",
                    "ERROR_ROW_DOES_NOT_EXIST",
                ]
            ),
            409: get_error_schema(["ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS"]),
            # DRF's own `Throttled` body carries a `detail`, not an `error`,
            # the same as the workspace invitations view.
            429: None,
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkflowActionDispatchInProgress: ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS,
            WorkflowActionDispatchError: ERROR_WORKFLOW_ACTION_DISPATCH_FAILED,
        }
    )
    @validate_body(DispatchWorkflowActionsSerializer)
    def post(self, request, data: Dict, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)
        row = RowHandler().get_row(request.user, field.table, data["row_id"])

        service = DatabaseWorkflowActionService()
        # Read once for the budget, the permission checks and the run, so all
        # three describe the same click.
        workflow_actions = service.get_dispatch_snapshot(field)
        reservations = self._reserve_dispatch_budget(request, field, workflow_actions)
        reached_outside = []

        try:
            dispatch = service.dispatch_workflow_actions(
                request.user,
                field,
                row,
                workflow_actions=workflow_actions,
                on_external_dispatch=reached_outside.append,
            )
        finally:
            # Charged for what the click really sent. Without this a member
            # who may not dispatch could spend the workspace's budget on
            # refusals, and a click that failed after its request could repeat
            # that request for free.
            self._release_dispatch_budget(reservations, keep=len(reached_outside))

        # A client action can read only what ran before it, so a result with
        # none after it is not sent at all. Configuring a button needs more
        # permission than clicking one, and an answer from outside Baserow
        # carries whatever the endpoint sent back, response headers included.
        last_client_position = max(
            (
                dispatch.positions.get(workflow_action.id) or 0
                for workflow_action in dispatch.client_actions
            ),
            default=0,
        )

        def is_wanted(dispatched):
            position = dispatch.positions.get(dispatched.workflow_action.id) or 0
            return 0 < position < last_client_position

        def field_names_for(dispatched):
            if not is_wanted(dispatched) or not isinstance(
                dispatched.result.data, dict
            ):
                return {}
            workflow_action = dispatched.workflow_action
            return workflow_action.get_type().get_result_field_names(workflow_action)

        results = [
            {
                "workflow_action_id": dispatched.workflow_action.id,
                # The browser only lets a client action read what ran before
                # it, and it has no other way to tell where an action sat.
                # `order` is what the action carries; `position` is where it
                # really ran, which is what two actions sharing an `order` are
                # told apart by.
                "order": dispatched.workflow_action.order,
                "position": dispatch.positions.get(dispatched.workflow_action.id),
                # Every action runs synchronously inside the request. The field
                # is here so an async one can report "dispatched" later.
                "status": "completed",
                "data": dispatched.result.data if is_wanted(dispatched) else None,
                "field_names": field_names_for(dispatched),
            }
            for dispatched in dispatch.dispatched
        ]

        return Response(
            {
                "results": results,
                "client_actions": [
                    database_workflow_action_type_registry.get_serializer(
                        workflow_action,
                        DispatchedClientActionSerializer,
                        # The position is on the same scale as a result's, so
                        # the browser can tell which results ran before this
                        # action.
                        context={
                            "user": request.user,
                            "positions": dispatch.positions,
                        },
                    ).data
                    for workflow_action in dispatch.client_actions
                ],
            }
        )
