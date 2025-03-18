from datetime import datetime, timezone
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin, PolymorphicContentTypeMixin

from .cache import job_progress_key
from .constants import JOB_CANCELLED, JOB_FAILED, JOB_FINISHED, JOB_PENDING, JOB_STARTED

User = get_user_model()

JOB_STATES_FAILED = (JOB_CANCELLED, JOB_FAILED)
JOB_STATES_ENDED = JOB_STATES_FAILED + (JOB_FINISHED,)
JOB_STATES_NOT_RUNNING = JOB_STATES_ENDED + (JOB_PENDING,)
JOB_STATES_RUNNING = (JOB_STARTED,)
JOB_STATES_PENDING = (JOB_PENDING,)


def get_default_job_content_type():
    return ContentType.objects.get_for_model(Job)


class JobQuerySet(models.QuerySet):
    def is_running(self):
        return self.exclude(state__in=JOB_STATES_NOT_RUNNING)

    def is_ended(self):
        return self.filter(state__in=JOB_STATES_ENDED)

    def is_pending_or_running(self):
        return self.exclude(state__in=JOB_STATES_ENDED)


class Job(CreatedAndUpdatedOnMixin, PolymorphicContentTypeMixin, models.Model):
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="database_jobs",
        on_delete=models.SET(get_default_job_content_type),
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="The user that has created the job"
    )
    progress_percentage = models.IntegerField(
        default=0,
        help_text="A percentage indicating how far along the job is. 100 means "
        "that it's finished.",
    )
    state = models.CharField(
        db_index=True,
        max_length=128,
        default=JOB_PENDING,
        help_text="Indicates the state of the job.",
    )
    error = models.TextField(
        blank=True, default="", help_text="An error message if something went wrong."
    )
    human_readable_error = models.TextField(
        blank=True,
        default="",
        help_text="A human readable error message indicating what went wrong.",
    )

    objects = JobQuerySet.as_manager()

    def get_from_cache(self) -> dict | None:
        """
        Returns cached state for the job. Cached state is set with
        Job.set_cached_state().

        If no state is present in cache, returns None.
        :return:
        """

        return cache.get(job_progress_key(self.id))

    def get_from_cached_value_or_from_self(self, name: str) -> Any:
        """
        Because the `progress_percentage` and `state` are updated via a transaction,
        we also temporarily store the progress in the Redis cache. This is needed
        because other database connection, for example a gunicorn worker, can't get
        the latest progress from the PostgreSQL table because it's updated in a
        transaction.

        This method tries to get the progress from the cache and if it's not found,
        it falls back on the job table entry data.

        :param name: The name in the cache entry dict.
        :return: The correct value.
        """

        return (self.get_from_cache() or {}).get(name, getattr(self, name))

    def get_cached_progress_percentage(self) -> int:
        return self.get_from_cached_value_or_from_self("progress_percentage")

    def get_cached_state(self) -> str:
        return self.get_from_cached_value_or_from_self("state")

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=["-updated_on"])]

    def set_cached_state(self):
        """
        Updates job progress cache key.
        """

        progress = {
            "progress_percentage": self.progress_percentage,
            "state": self.state,
            "updated_on": datetime.now(tz=timezone.utc),
        }
        cache.set(job_progress_key(self.id), progress, timeout=None)

    def set_state(
        self, state: str, error: str | None = None, message: str | None = None
    ):
        """
        Helper method to set a state on a job.

        :param state: One of JOB_* states
        :param error: Short error message
        :param message: Longer, human readable error description
        """

        self.state = state
        if error is not None:
            self.error = error
        if message is not None:
            self.human_readable_error = message
        self.set_cached_state()

    def set_state_cancelled(self):
        """
        Mark job as pending cancellatttion
        """

        self.set_state(JOB_CANCELLED)

    def set_state_failed(self, error: str, message: str):
        """
        Mark job as failed with an error.

        :param error: Short error message.
        :param message: Longer, human readable error description.
        """

        self.set_state(JOB_FAILED, error, message)

    def set_state_started(self):
        """
        Mark job as started
        """

        self.set_state(JOB_STARTED)

    def set_state_finished(self):
        """
        Mark job as started
        """

        self.set_state(JOB_FINISHED)

    @property
    def last_updated_on(self) -> datetime | None:
        return self.get_from_cached_value_or_from_self("updated_on")

    @property
    def pending(self) -> bool:
        return self.get_cached_state() == JOB_PENDING

    @property
    def failed(self) -> bool:
        return self.get_cached_state() == JOB_FAILED

    @property
    def cancelled(self) -> bool:
        return self.get_cached_state() == JOB_CANCELLED

    @property
    def started(self) -> bool:
        return self.get_cached_state() == JOB_STARTED

    @property
    def finished(self) -> bool:
        return self.get_cached_state() == JOB_FINISHED

    @property
    def ended(self):
        return self.get_cached_state() in JOB_STATES_ENDED

    def clear_job_cache(self):
        """
        Clears job's cache entries.
        """

        cache.delete(job_progress_key(self.id))
