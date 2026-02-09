from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Type

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import Q, QuerySet

from baserow.core.utils import Progress

from .exceptions import JobCancelled, JobDoesNotExist, JobNotCancellable
from .models import Job
from .registries import job_type_registry
from .signals import job_started
from .tasks import run_async_job
from .types import AnyJob


class JobHandler:
    @classmethod
    def cancel_job(cls, job: AnyJob) -> Job | None:
        """
        Marks a job for cancellation. It will mark the job as cancelled, but won't
        cancel a Celery task directly. The task's responsible to drop job's processing
        as soon as it detects the marker.

        :param job: The job to cancel.
        :return: The job that was marked for cancellation.
        :raises JobNotCancellable: If the job is already finished or failed, and
            cannot be cancelled.
        """

        if job.cancelled:
            return
        elif job.ended:
            raise JobNotCancellable()

        job.set_state_cancelled()
        job.save()
        return job

    @classmethod
    def run(cls, job: AnyJob):
        def progress_updated(percentage, state):
            """
            Every time the progress of the job changes, this callback function is
            called. If the percentage or the state has changed, the job will be updated.
            """

            nonlocal job

            # Periodically check for a job cancellation marker. Users can cancel jobs
            # via the UI, but this won't stop tasks already running in Celery. To handle
            # cancellations within a worker, the JobType.run method should periodically
            # check for a cancellation marker, either manually or whenever Progress
            # methods are called.
            if job.cancelled:
                raise JobCancelled()
            job.progress_percentage = percentage

            if state:
                job.set_state(state)
            job.set_cached_state()

        progress = Progress(100)
        progress.register_updated_event(progress_updated)

        job_started.send(JobHandler, job=job, user=job.user)

        job_type = job_type_registry.get_by_model(job)
        out = job_type.run(job, progress)

        # Final check if the job was cancelled because we don't want to overwrite the
        # state if the `job_type.run` didn't notice the cancellation.
        if job.cancelled:
            raise JobCancelled()

        return out

    @classmethod
    def get_job(
        cls,
        user: AbstractUser,
        job_id: int,
        job_model: Optional[Type[AnyJob]] = None,
        base_queryset: Optional[QuerySet] = None,
    ) -> Job:
        """
        Returns the job corresponding to the given id.

        :param job_id: The job id we want to fetch.
        :param job_model: An optional Job model.
        :param base_queryset: An optional base queryset to use instead of the default
            one.
        :return: the job.
        """

        if not job_model:
            job_model = Job

        if base_queryset is None:
            base_queryset = job_model.objects

        try:
            return base_queryset.select_related("user").get(id=job_id, user_id=user.id)
        except Job.DoesNotExist:
            raise JobDoesNotExist(f"The job with id {job_id} does not exist.")

    @classmethod
    def get_jobs_for_user(
        cls,
        user: AbstractUser,
        filter_states: Optional[List[str]],
        filter_ids: Optional[List[int]],
        base_model: Optional[Type[AnyJob]] = None,
        type_filters: Optional[Dict[str, Any]] = None,
    ) -> QuerySet:
        """
        Returns all jobs belonging to the specified user.

        :param user: The user we want the jobs for.
        :param filter_states: A list of states that the jobs should have, or not
            have if prefixed with a !.
        :param filter_ids: A list of specific job ids to return.
        :param base_model: An optional Job model.
        :param type_filters: Optional type-specific filters (e.g., field_id for
            GenerateAIValuesJob).
        :return: A QuerySet with the filtered jobs for the user.
        """

        if base_model is None:
            base_model = Job

        def get_job_states_filter(states):
            states_q = Q()
            for state in states:
                if state.startswith("!"):
                    states_q &= ~Q(state=state[1:])
                else:
                    states_q |= Q(state=state)
            return states_q

        queryset = base_model.objects.filter(user=user).order_by("-id")

        if filter_states:
            queryset = queryset.filter(get_job_states_filter(filter_states))

        if filter_ids:
            queryset = queryset.filter(id__in=filter_ids)

        if type_filters:
            queryset = queryset.filter(**type_filters)

        return queryset.select_related("content_type")

    @classmethod
    def get_pending_or_running_jobs(
        cls,
        job_type_name: str,
    ) -> QuerySet:
        """
        Returns a queryset of pending or running jobs of a provided job type
        that can be further filtered.

        :param job_type_name: The job type for which we want the queryset.
        :return: Queryset of all pending or running jobs of the job type.
        """

        job_type = job_type_registry.get(job_type_name)
        model_class = job_type.model_class
        return model_class.objects.filter().is_pending_or_running()

    def create_and_start_job(
        self, user: AbstractUser, job_type_name: str, sync=False, **kwargs
    ) -> Job:
        """
        Creates a new job and schedule the asynchronous task.

        :param user: The user whom launch the task.
        :param job_type_name: The job type we want to launch.
        :param sync: True if you want to execute the job immediately.

        :return: The newly created job.
        """

        job_type = job_type_registry.get(job_type_name)
        model_class = job_type.model_class
        job_values = job_type.prepare_values(kwargs, user)
        job: AnyJob = model_class(user=user, **job_values)
        job_type.can_schedule_or_raise(job)
        job.save()
        job_type.after_job_creation(job, kwargs)

        if sync:
            run_async_job(job.id)
            job.refresh_from_db()
        else:
            # This wrapper ensure the job doesn't stay in pending state if something
            # goes wrong during the delay call. This is related to the redis connection
            # failure that triggers a sys.exit(1) to be called in gunicorn.
            def call_async_job_safe():
                try:
                    run_async_job.delay(job.id)
                except BaseException as e:
                    job.refresh_from_db()
                    if job.pending:
                        job.set_state_failed(
                            str(e),
                            f"Something went wrong during the job({job.id}) execution.",
                        )
                        job.save()
                    raise

            transaction.on_commit(call_async_job_safe)

        return job

    def clean_up_jobs(self):
        """
        Terminate running jobs after the soft limit and delete expired jobs.
        """

        # Delete old job
        now = datetime.now(tz=timezone.utc)
        limit_date = now - timedelta(
            minutes=(settings.BASEROW_JOB_EXPIRATION_TIME_LIMIT)
        )
        for job_to_delete in Job.objects.filter(created_on__lte=limit_date).is_ended():
            self.delete_job(job_to_delete.specific)

        # Expire non expired jobs
        limit_date = now - timedelta(seconds=(settings.BASEROW_JOB_SOFT_TIME_LIMIT + 1))

        #  Use updated_on instead of created_on to verify the last update date
        # but use the cache since the DB is not updated until the end of the transaction
        jobs_to_update = []
        for job in Job.objects.filter(
            created_on__lte=limit_date
        ).is_pending_or_running():
            if (
                last_updated_on := job.last_updated_on
            ) and last_updated_on < limit_date:
                job.set_state_failed(
                    "Timeout error",
                    "Something went wrong during the job execution.",
                )
                # Set the updated_on manually because it won't be set by bulk_update
                job.updated_on = now
                jobs_to_update.append(job)
        if jobs_to_update:
            Job.objects.bulk_update(
                jobs_to_update,
                fields=["updated_on", "state", "error", "human_readable_error"],
            )

    @classmethod
    def delete_job(cls, job: Type[Job]):
        """
        Deletes a job, calls the job type's before_delete method and clears the job
        cache.

        :param job: The specific job to delete.
        """

        job_type = job_type_registry.get_by_model(job)
        job_type.before_delete(job)
        job.clear_job_cache()
        job.delete()
