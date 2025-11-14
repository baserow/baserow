from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body_custom_fields,
    validate_query_parameters,
)
from baserow.api.schemas import get_error_schema
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.core.db import specific_iterator
from baserow.core.jobs.exceptions import (
    JobDoesNotExist,
    JobNotCancellable,
    MaxJobCountExceeded,
)
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry

from .errors import (
    ERROR_JOB_DOES_NOT_EXIST,
    ERROR_JOB_NOT_CANCELLABLE,
    ERROR_MAX_JOB_COUNT_EXCEEDED,
)
from .serializers import CreateJobSerializer, JobSerializer, ListJobQuerySerializer


class JobsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[ListJobQuerySerializer],
        tags=["Jobs"],
        operation_id="list_job",
        description=(
            "List all existing jobs. Jobs are task executed asynchronously in the "
            "background. You can use the `get_job` endpoint to read the current "
            "progress of the job. The available query parameters depend on the job type "
            "selected via the `type` parameter. Each job type may support additional "
            "type-specific filter parameters."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                job_type_registry, JobSerializer, many=True
            )
        },
    )
    @validate_query_parameters(ListJobQuerySerializer, return_validated=True)
    def get(self, request, query_params):
        states = query_params.get("states", None)
        job_ids = query_params.get("job_ids", None)
        offset = query_params.get("offset", 0)
        limit = query_params.get("limit", 20)

        # Get job type and filters from the validated data
        job_type_name = query_params.get("job_type_name", None)
        type_filters = query_params.get("type_filters", {})

        base_model = None
        if job_type_name:
            job_type = job_type_registry.get(job_type_name)
            base_model = job_type.model_class

        jobs = JobHandler.get_jobs_for_user(
            request.user,
            filter_states=states,
            filter_ids=job_ids,
            base_model=base_model,
            type_filters=type_filters if type_filters else None,
        )[offset : offset + limit]

        serialized_jobs = [
            job_type_registry.get_serializer(
                job,
                JobSerializer,
                context={"request": request},
            ).data
            for job in specific_iterator(jobs)
        ]
        return Response({"jobs": serialized_jobs})

    @extend_schema(
        tags=["Jobs"],
        operation_id="create_job",
        description=(
            "Creates a new job. This job runs asynchronously in the "
            "background and execute the task specific to the provided type"
            "parameters. The `get_job` can be used to get the current state "
            "of the job."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            job_type_registry,
            CreateJobSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                job_type_registry, JobSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_GROUP_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @validate_body_custom_fields(
        job_type_registry, base_serializer_class=CreateJobSerializer
    )
    @map_exceptions(
        {
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    def post(self, request, data):
        """Creates a new job."""

        type_name = data.pop("type")
        job_type = job_type_registry.get(type_name)

        # Because each type can raise custom exceptions while creating the
        # job we need to be able to map those to the correct API exceptions which are
        # defined in the type.
        with job_type.map_api_exceptions():
            job = JobHandler().create_and_start_job(request.user, type_name, **data)

        serializer = job_type.get_serializer(
            job,
            JobSerializer,
            context={"request": request},
        )
        return Response(serializer.data)


class JobView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="job_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The job id to lookup information about.",
            )
        ],
        tags=["Jobs"],
        operation_id="get_job",
        description=(
            "Returns the information related to the provided job id. "
            "This endpoint can for example be polled to get the state and progress of "
            "the job in real time."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                job_type_registry, JobSerializer
            ),
            404: get_error_schema(["ERROR_JOB_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            JobDoesNotExist: ERROR_JOB_DOES_NOT_EXIST,
        }
    )
    def get(self, request, job_id):
        """Returns the job related to the provided id."""

        job = JobHandler.get_job(request.user, job_id)
        serializer = job_type_registry.get_serializer(
            job.specific,
            JobSerializer,
            context={"request": request},
        )
        return Response(serializer.data)


class CancelJobView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="job_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The job id to cancel.",
            )
        ],
        tags=["Jobs"],
        operation_id="cancel_job",
        description=(
            "Cancels a job. Note: you can cancel only "
            "a scheduled or a job that is already running. The user "
            "requesting must be the owner of the job to cancel."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                job_type_registry, JobSerializer
            ),
            400: get_error_schema(["ERROR_JOB_NOT_CANCELLABLE"]),
            404: get_error_schema(["ERROR_JOB_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            JobDoesNotExist: ERROR_JOB_DOES_NOT_EXIST,
            JobNotCancellable: ERROR_JOB_NOT_CANCELLABLE,
        }
    )
    def post(self, request, job_id):
        """Cancels a job.

        This endpoint can be used to cancel a job that is currently running or
        scheduled to run. The user requesting must be the owner of the job to
        cancel.
        """

        job = JobHandler.get_job(request.user, job_id)
        JobHandler.cancel_job(job)

        serializer = job_type_registry.get_serializer(
            job.specific,
            JobSerializer,
            context={"request": request},
        )
        return Response(serializer.data)
