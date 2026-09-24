from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.contrib.builder.api.domains.errors import ERROR_DOMAIN_DOES_NOT_EXIST
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.integrations.exceptions import IntegrationImproperlyConfigured
from baserow.core.jobs.registries import JobType
from baserow.core.registries import application_type_registry

from .exceptions import DomainDoesNotExist
from .models import PublishDomainJob


class PublishDomainJobType(JobType):
    """
    Asynchronously executes a domain publishing operation.
    """

    type = "publish_domain"
    model_class = PublishDomainJob
    max_count = 2
    job_exceptions_map = {
        IntegrationImproperlyConfigured: "The application contains an improperly "
        "configured integration: {e}"
    }

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        DomainDoesNotExist: ERROR_DOMAIN_DOES_NOT_EXIST,
    }

    def transaction_atomic_context(self, job: PublishDomainJob):
        # It's possible for the Domain to be deleted prior to the execution of
        # this task (e.g. the export worker queue is down, and brought up again).
        if not job.domain:
            raise DomainDoesNotExist(
                "The Domain has been deleted prior to the execution of this task."
            )
        application_type = application_type_registry.get("builder")
        return application_type.export_safe_transaction_context(job.domain.builder)

    def run(self, job: PublishDomainJob, progress):
        from .service import DomainService

        DomainService().publish(job.user, job.domain, progress)
