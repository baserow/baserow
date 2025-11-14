from typing import Any, Dict, Type

from django.contrib.auth.models import AbstractUser

from opentelemetry import trace
from rest_framework import serializers

from baserow.core.db import transaction_atomic
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    MapAPIExceptionsInstanceMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.utils import Progress

from .exceptions import (
    JobTypeAlreadyRegistered,
    JobTypeDoesNotExist,
    MaxJobCountExceeded,
)
from .models import Job
from .types import AnyJob

tracer = trace.get_tracer(__name__)


class JobType(
    CustomFieldsInstanceMixin,
    ModelInstanceMixin,
    MapAPIExceptionsInstanceMixin,
    Instance,
    metaclass=baserow_trace_methods(tracer, only="do"),
):

    """
    This abstract class represents a custom job type that can be added to the
    job type registry. It must be extended so customization can be done. Each job
    type will have its own `run` method that will be run asynchronously.
    """

    job_exceptions_map = {}

    """
    A map of exception that can be used to map exceptions to certain task error
    messages.
    """

    max_count: int = 1

    """
    A number of max jobs count for the same type for a given user.
    """

    def can_schedule_or_raise(self, job: Job) -> None:
        """
        This method can be overridden to add custom logic to check if the given user
        can schedule a job of this type.

        :param job: The job instance that is going to be scheduled.
        :raises MaxJobCountExceeded: If the user cannot schedule a new job of this type.
        """

        # Check how many job of same type are running simultaneously. If count > max
        # we don't want to create a new one.
        running_jobs = job.__class__.objects.filter(
            user_id=job.user.id
        ).is_pending_or_running()

        if len(running_jobs) >= self.max_count:
            raise MaxJobCountExceeded(
                f"You can only launch {self.max_count} {self.type} job(s) at "
                "the same time."
            )

    def transaction_atomic_context(self, job: Job):
        """
        This method gives the possibility to change the transaction context per request.
        """

        return transaction_atomic()

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        """
        The prepare_values hook gives the possibility to change the provided values
        that just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object. It's also an opportunity to add
        specific validations.

        :param values: The provided values.
        :param user: The user on whose behalf the change is made.
        :return: The updated values.
        """

        return values

    def after_job_creation(self, job: AnyJob, values: Dict[str, Any]):
        """
        This method gives the possibility to change the job just after the
        instance creation. For example, files can be saved, or relationship can be
        added.

        :param job: The created job.
        :param values: The provided values.
        """

    def run(self, job: AnyJob, progress: Progress) -> Any:
        """
        This method is the task of this job type that will be executed asynchronously.

        :param job: the specific instance of the related job instance
        :param progress: A progress object that can be used to track the progress of
          the task.
        """

        raise NotImplementedError("The run method must be implemented.")

    def before_delete(self, job: AnyJob):
        """
        If a job type need to do something before a job deletion, can be done here.
        This method is do nothing by default.
        """

    def on_error(self, job: AnyJob, error: Exception):
        """
        This method gives the possibility to change the job after an exception has
        been raised. This happens after the transaction so database changes are kept.

        :param job: the specific instance of the related job instance
        :param error: the exception raised.
        """

    @property
    def request_serializer_class(self):
        """
        The serializer that must be used to validate the request data before
        creating a new job instance of this type.
        """

        return self.get_serializer_class(
            base_class=serializers.Serializer,
            request_serializer=True,
            meta_ref_name=f"{self.__class__.__name__}RequestSerializer",
        )

    @property
    def response_serializer_class(self):
        """
        The serializer that must be used to serialize the response data of the job
        instance of this type.
        """

        from baserow.api.jobs.serializers import JobSerializer

        return self.get_serializer_class(
            base_class=JobSerializer,
            meta_ref_name=f"{self.__class__.__name__}ResponseSerializer",
        )

    def get_filters_serializer(self) -> Type[serializers.Serializer] | None:
        """
        This method enables job types to define custom filters for job listing
        operations. Since query parameters cannot utilize Discriminator fields and must
        be flattened, all filter field names should be prefixed with the job type name
        followed by an underscore to prevent naming conflicts between different job
        types.

        :return: A serializer class extending JobTypeFiltersSerializer, or None if no
                 type-specific filters are needed.
        """

        return None


class JobTypeRegistry(
    CustomFieldsRegistryMixin,
    ModelRegistryMixin[Job, JobType],
    Registry[JobType],
):
    """
    The registry that holds all the available job types.
    """

    name = "job_type"

    does_not_exist_exception_class = JobTypeDoesNotExist
    already_registered_exception_class = JobTypeAlreadyRegistered


job_type_registry: JobTypeRegistry = JobTypeRegistry()
