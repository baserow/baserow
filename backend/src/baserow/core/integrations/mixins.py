from typing import Any, Dict, Optional

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


class IntegrationConsumerMixin:
    """
    For a type whose instances read through an integration, such as a service or a
    user source: resolves the `integration_id` it's given, and validates the
    integration against the application the instance belongs to.
    """

    # The integration type instances read through, or `None` if any type is
    # accepted.
    integration_type: Optional[str] = None

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
                    raise _invalid_integration(
                        f"The integration with ID {integration_id} does not exist."
                    ) from exc

        return values

    def check_integration(self, application: Application, values: Dict[str, Any]):
        """
        Validates that the prepared integration belongs to the given application and
        is of `integration_type`.

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
            raise _invalid_integration(
                f"The integration with ID {integration.id} is not related to the "
                f"given application {application.id}."
            ) from exc
        except IntegrationTypeNotAllowed as exc:
            raise _invalid_integration(
                f"The integration with ID {integration.id} is not a "
                f"{self.integration_type} integration."
            ) from exc
