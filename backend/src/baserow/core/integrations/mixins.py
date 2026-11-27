from typing import Any, Dict, Optional

from django.contrib.auth.models import AbstractUser

from baserow.api.exceptions import RequestBodyValidationException
from baserow.core.integrations.exceptions import (
    IntegrationDoesNotExist,
    IntegrationNotInApplication,
    IntegrationTypeNotAllowed,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.models import Application


def _invalid_integration(detail: str) -> RequestBodyValidationException:
    return RequestBodyValidationException(
        {"integration_id": [{"detail": detail, "code": "invalid_integration"}]}
    )


def _integration_does_not_exist(integration_id: int) -> RequestBodyValidationException:
    return _invalid_integration(
        f"The integration with ID {integration_id} does not exist."
    )


class IntegrationConsumerMixin:
    """
    For a type whose instances read through an integration, such as a service or a
    user source: resolves the `integration_id` it's given, and validates the
    integration against the application the instance belongs to.
    """

    # The integration type instances read through, or `None` if any type is
    # accepted.
    integration_type: Optional[str] = None

    def with_default_integration(
        self, values: Dict[str, Any], user: AbstractUser, application: Application
    ) -> Dict[str, Any]:
        """Supply an unambiguous integration for a new consumer or type change.

        Call before preparing values so service-specific modes can still discard
        the default. Existing choices, including unavailable references, survive.
        Ordinary edits must not call this method, so clearing a choice stays valid.
        """
        from baserow.core.integrations.service import IntegrationService

        values = values.copy()
        if not values.get("integration_id") and not values.get("integration"):
            integration = IntegrationService().get_default_integration(
                user, application, self.integration_type
            )
            if integration is not None:
                values["integration_id"] = integration.id
        return values

    def prepare_integration_values(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replaces `integration_id` in the values with the integration. A trashed
        integration is resolved too, so undoing an update can restore it.

        :param values: The provided values.
        :raises RequestBodyValidationException: When the integration doesn't exist.
        :return: The updated values.
        """

        if "integration_id" in values:
            integration_id = values.pop("integration_id")
            if integration_id is None:
                values["integration"] = None
            else:
                try:
                    values["integration"] = (
                        IntegrationHandler().get_integration_including_trashed(
                            integration_id
                        )
                    )
                except IntegrationDoesNotExist as exc:
                    raise _integration_does_not_exist(integration_id) from exc

        return values

    def resolve_integration(
        self, application: Application, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Replaces `integration_id` in the values with the integration, and validates
        it against the application. Called before `prepare_values`, so that no
        validation of the type reads through an integration of another application.

        :param application: The application the instance belongs to.
        :param values: The provided values.
        :raises RequestBodyValidationException: When the integration doesn't exist,
            or doesn't fit.
        :return: The updated values.
        """

        values = self.prepare_integration_values(values)
        self.check_integration(application, values)
        return values

    def check_integration(self, application: Application, values: Dict[str, Any]):
        """
        Validates that the prepared integration can be used from the given
        application, being its own or a workspace integration of its workspace, and is
        of `integration_type`. An integration the application can't use is answered
        like one that doesn't exist, so that the answer says nothing about what
        another application holds.

        :param application: The application the instance belongs to.
        :param values: The prepared values, as returned by `prepare_values`.
        :raises RequestBodyValidationException: When the integration doesn't fit.
        """

        integration = values.get("integration")
        if integration is None:
            return

        try:
            IntegrationHandler().check_integration_usable(
                integration,
                application_id=application.id,
                integration_types=(
                    None if self.integration_type is None else [self.integration_type]
                ),
            )
        except IntegrationNotInApplication as exc:
            raise _integration_does_not_exist(integration.id) from exc
        except IntegrationTypeNotAllowed as exc:
            raise _invalid_integration(
                f"The integration with ID {integration.id} is not a "
                f"{self.integration_type} integration."
            ) from exc
