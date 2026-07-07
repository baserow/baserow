from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Tuple

from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class ApplicationUserUsageProviderType(Instance, ABC):
    """
    Resolves the current application user usage and the limit for a workspace.

    The application user limit lives in different places depending on the deployment
    (a per-workspace quota for SaaS, an instance-wide license value for self-hosted
    enterprise). Plugins register a provider so that the application user limit can be
    enforced and notified about without knowing where the limit value comes from.
    """

    # The provider with the highest order that returns a non-None result wins. On the
    # SaaS platform both the SaaS per-workspace provider and the premium instance-wide
    # provider are registered (the saas plugin runs on top of enterprise), so the SaaS
    # provider uses a higher order to take precedence. A genuine self-hosted install
    # only registers the premium provider, since the saas plugin isn't part of it.
    order = 0

    @abstractmethod
    def get_usage_and_limit(
        self, workspace: "Workspace"
    ) -> Optional[Tuple[int, Optional[int]]]:
        """
        Returns a `(usage, limit)` tuple for the given workspace, or `None` when this
        provider does not apply to the current deployment. A `limit` of `None` means
        there is no enforced application user limit.

        :param workspace: The workspace a new application user would belong to.
        :return: A `(usage, limit)` tuple or `None`.
        """

    def get_login_limit(self, workspace: "Workspace") -> Optional[int]:
        """
        Returns the application user limit to enforce at login time for the given
        workspace, or `None` when this provider does not enforce a hard login limit
        for the current deployment.

        When a limit is returned, only the first `limit` users (ordered by creation)
        of a user source are allowed to authenticate; the rest are refused. This is
        separate from `get_usage_and_limit` (used for notifications) because a
        deployment can notify about its limit without hard-blocking logins. Defaults
        to `None` so a provider only opts into hard login enforcement when it returns
        a value.

        :param workspace: The workspace the authenticating user belongs to.
        :return: The login limit, or `None`.
        """

        return None


class ApplicationUserUsageProviderRegistry(Registry):
    """
    Contains the registered application user usage providers.
    """

    name = "application_user_usage_provider"


application_user_usage_provider_registry: ApplicationUserUsageProviderRegistry = (
    ApplicationUserUsageProviderRegistry()
)
