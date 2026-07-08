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

    def is_over_login_limit(self, workspace: "Workspace") -> Optional[bool]:
        """
        Returns whether the given workspace is over this provider's application user
        limit, or None when this provider doesn't enforce a hard login limit.

        When True, all logins to the workspace's user sources are refused, not just
        the users past the limit.

        The default implementation derives the verdict from get_usage_and_limit(),
        so a provider that resolves a usage/limit automatically enforces the hard
        block.

        :param workspace: The workspace the authenticating user belongs to.
        :return: `True`/`False` when this provider enforces a hard login limit, or
            `None` when it doesn't.
        """

        # None when this provider can't resolve a usage/limit for the deployment, so
        # it doesn't apply and the next provider should decide. The premium provider,
        # for instance, returns None on an unlicensed or pre v1.32 install where no
        # active license carries an application_users limit.
        result = self.get_usage_and_limit(workspace)
        if result is None:
            return None

        # A limit of None means the provider applies but the deployment enforces no
        # limit of its own. We return None (defer) rather than False (allow) because
        # "no limit here" isn't the same as "the login is fine": returning False would
        # short-circuit the caller and stop it from consulting the remaining providers,
        # one of which may enforce a limit. Deferring lets a lower-order provider still
        # have its say.
        usage, limit = result
        if limit is None:
            return None

        return usage > limit


class ApplicationUserUsageProviderRegistry(Registry):
    """
    Contains the registered application user usage providers.
    """

    name = "application_user_usage_provider"


application_user_usage_provider_registry: ApplicationUserUsageProviderRegistry = (
    ApplicationUserUsageProviderRegistry()
)
