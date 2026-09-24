from time import perf_counter
from typing import Dict, List

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http_status
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
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.services.errors import ERROR_SERVICE_INVALID_TYPE
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
    ERROR_WORKFLOW_ACTION_INVALID_INTEGRATION,
    ERROR_WORKFLOW_ACTION_NOT_IN_FIELD,
    ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED,
)
from baserow.contrib.database.api.workflow_actions.serializers import (
    CreateDatabaseWorkflowActionSerializer,
    DatabaseWorkflowActionSerializer,
    DispatchWorkflowActionsResponseSerializer,
    DispatchWorkflowActionsSerializer,
    OrderWorkflowActionsSerializer,
    UpdateDatabaseWorkflowActionSerializer,
    dispatch_result_payload,
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
from baserow.contrib.database.workflow_actions.actions import (
    CreateDatabaseWorkflowActionActionType,
    DeleteDatabaseWorkflowActionActionType,
    OrderDatabaseWorkflowActionsActionType,
    UpdateDatabaseWorkflowActionActionType,
)
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
    WorkflowActionInvalidIntegration,
    WorkflowActionNotInField,
    WorkflowActionTypeDeactivated,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.job_types import (
    ButtonFieldDispatchJobType,
)
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.signals import (
    button_field_dispatched,
    workflow_actions_before_dispatch,
)
from baserow.contrib.database.workflow_actions.telemetry import (
    outcome_for,
)
from baserow.contrib.database.workflow_actions.types import DispatchOutcome
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.services.exceptions import ServiceTypeDoesNotExist
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
                    "ERROR_WORKFLOW_ACTION_INVALID_INTEGRATION",
                    "ERROR_SERVICE_INVALID_TYPE",
                ]
            ),
            403: get_error_schema(["ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkflowActionTypeDeactivated: ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED,
            WorkflowActionInvalidIntegration: ERROR_WORKFLOW_ACTION_INVALID_INTEGRATION,
            ServiceTypeDoesNotExist: ERROR_SERVICE_INVALID_TYPE,
        }
    )
    @validate_body_custom_fields(
        database_workflow_action_type_registry,
        base_serializer_class=CreateDatabaseWorkflowActionSerializer,
        serializer_class_context={"application_type": DatabaseApplicationType},
    )
    def post(self, request, data: Dict, field_id: int):
        type_name = data.pop("type")
        workflow_action_type = database_workflow_action_type_registry.get(type_name)
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_action = action_type_registry.get(
            CreateDatabaseWorkflowActionActionType.type
        ).do(request.user, workflow_action_type, field, **data)

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
        # Locked, so a second delete of the same action waits for the first and
        # then finds no action, rather than trashing it twice.
        workflow_action = (
            DatabaseWorkflowActionHandler().get_workflow_action_for_update(
                workflow_action_id
            )
        )

        action_type_registry.get(DeleteDatabaseWorkflowActionActionType.type).do(
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
                    "ERROR_WORKFLOW_ACTION_INVALID_INTEGRATION",
                    "ERROR_SERVICE_INVALID_TYPE",
                ]
            ),
            403: get_error_schema(["ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED"]),
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
            WorkflowActionTypeDeactivated: ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED,
            WorkflowActionInvalidIntegration: ERROR_WORKFLOW_ACTION_INVALID_INTEGRATION,
            ServiceTypeDoesNotExist: ERROR_SERVICE_INVALID_TYPE,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, workflow_action_id: int):
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

        workflow_action_updated = action_type_registry.get(
            UpdateDatabaseWorkflowActionActionType.type
        ).do(request.user, workflow_action, **data)

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
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        action_type_registry.get(OrderDatabaseWorkflowActionsActionType.type).do(
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

        Reserved up front, the only way a limit holds under a burst. A limit
        that denies mid way gives back what came before it.

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

    def _release_dispatch_budget(self, reservations: List[list]) -> None:
        """
        Gives back every slot of a click refused before its job was created.

        :param reservations: What `_reserve_dispatch_budget` took, one list per
            limit.
        """

        for held in reservations:
            for throttle in held:
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
            "given row, and returns one result per action. When any action "
            "reaches outside Baserow, the click runs in a job instead and "
            "the response is a 202 with that job."
        ),
        request=DispatchWorkflowActionsSerializer,
        responses={
            200: DispatchWorkflowActionsResponseSerializer,
            # Returned instead of 200 when any workflow action of the button
            # reaches outside Baserow: the click runs in a job, returned here
            # in its pending state.
            202: ButtonFieldDispatchJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            403: get_error_schema(["ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED"]),
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
            WorkflowActionTypeDeactivated: ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED,
            WorkflowActionDispatchInProgress: ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS,
            WorkflowActionDispatchError: ERROR_WORKFLOW_ACTION_DISPATCH_FAILED,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    @validate_body(DispatchWorkflowActionsSerializer)
    def post(self, request, data: Dict, field_id: int):
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        started = perf_counter()
        workflow_actions: List[DatabaseWorkflowAction] = []
        failed_positions: List[int] = []

        def send_dispatched(outcome, failed_position=None):
            # Refused clicks leave no audit entry, so this is the only place
            # they are counted.
            button_field_dispatched.send_robust(
                self.__class__,
                user=request.user,
                field=field,
                row_id=data["row_id"],
                workflow_actions=workflow_actions,
                outcome=outcome,
                failed_position=failed_position,
                # Only a click that reaches outside Baserow can get an error
                # status back, and the job counts those itself.
                error_status_count=0,
                duration_ms=(perf_counter() - started) * 1000,
            )

        error = None
        enqueued = False
        try:
            row = RowHandler().get_row(request.user, field.table, data["row_id"])

            service = DatabaseWorkflowActionService()
            # Read once for the budget, the permission checks and the run, so all
            # three describe the same click.
            workflow_actions = service.get_dispatch_snapshot(field)
            # Anything that waits on the other side runs behind the request,
            # so no worker is held while an endpoint answers (#6134). A button
            # that only touches rows, or only opens a URL, stays inline.
            if any(wa.get_type().is_external for wa in workflow_actions):
                enqueued = True
                response = self._enqueue_click(
                    request, field, row, service, workflow_actions
                )
            else:
                response = self._run_click(
                    request, field, row, service, workflow_actions, failed_positions
                )
        except Exception as exc:
            error = exc
        except BaseException:
            # A worker timeout, for instance, must not go uncounted.
            send_dispatched(DispatchOutcome.ERROR, next(iter(failed_positions), None))
            raise

        # Sent outside the `except`, so a receiver's own failure does not carry
        # the click's, whose message can name the address an action reached.
        # Not for someone outside the workspace: anyone could send those, each
        # tagged with another workspace's ids.
        if error is None:
            # The job reports its own outcome once it has run.
            if not enqueued:
                send_dispatched(DispatchOutcome.COMPLETED)
        elif not isinstance(error, UserNotInWorkspace):
            outcome, failed_position = outcome_for(error)
            send_dispatched(
                outcome, failed_position or next(iter(failed_positions), None)
            )

        if error is not None:
            raise error
        return response

    def _enqueue_click(
        self,
        request,
        field: ButtonField,
        row,
        service: DatabaseWorkflowActionService,
        workflow_actions: List[DatabaseWorkflowAction],
    ) -> Response:
        """
        Hands the click to a job and answers 202 with it. Refuses first what
        the job would refuse, so a click that cannot run leaves no job behind.

        A pending or started job row guards its cell from enqueue until the
        job ends, so a second click on that cell is refused. The short enqueue
        lock only serializes that check with the job's creation, so two
        racing clicks cannot both pass it.

        The rate-limit slots are charged for every external action once the
        job exists, and not given back after that: a refund needs this
        request's throttle objects, which the job does not have, and
        over-counting a click whose job later fails is the conservative
        direction for a limit. A refusal still inside this request, such as
        the per-user job cap or a job row that could not be written, gives its
        slots back like every other in-request refusal, since no job was ever
        created to charge them to.
        """

        service.check_dispatch_allowed(request.user, field, workflow_actions)
        # Before anything is charged, so a receiver refusing the click (a SaaS
        # quota) answers in the request as it does for an inline click. Sent
        # again when the job runs, in case the answer changed meanwhile.
        workflow_actions_before_dispatch.send(
            service,
            user=request.user,
            field=field,
            workflow_actions=tuple(
                wa for wa in workflow_actions if not wa.get_type().is_frontend_only
            ),
        )

        # Two requests could otherwise both see the cell free and both create
        # a job, which a single worker would then run one after the other,
        # sending every request twice.
        with service.cell_lock("button_enqueue", field, row.id, timeout=10):
            # A click already waiting or running on this cell.
            if service.has_click_in_flight(field, row.id, workflow_actions):
                raise WorkflowActionDispatchInProgress()

            reservations = self._reserve_dispatch_budget(
                request, field, workflow_actions
            )

            try:
                # The job runs this list and no other: it was checked and
                # charged for exactly these actions.
                job = JobHandler().create_and_start_job(
                    request.user,
                    ButtonFieldDispatchJobType.type,
                    field=field,
                    row_id=row.id,
                    accepted_actions=service.accepted_actions(workflow_actions),
                )
            except Exception:
                # No job was created to charge these slots to, whether the cap
                # refused it or its row could not be written.
                self._release_dispatch_budget(reservations)
                raise

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=http_status.HTTP_202_ACCEPTED)

    def _run_click(
        self,
        request,
        field: ButtonField,
        row,
        service: DatabaseWorkflowActionService,
        workflow_actions: List[DatabaseWorkflowAction],
        failed_positions: List[int],
    ) -> Response:
        """
        Runs a click none of whose actions reaches outside Baserow, inside the
        request. Such a click spends no rate-limit budget, so nothing is
        reserved or given back here.
        """

        dispatch = service.dispatch_workflow_actions(
            request.user,
            field,
            row,
            workflow_actions=workflow_actions,
            on_action_failed=failed_positions.append,
        )
        return Response(dispatch_result_payload(dispatch, request.user))
