from typing import TYPE_CHECKING, Optional

from baserow.core.registry import Instance, Registry

if TYPE_CHECKING:
    from .inbound_email import InboundEmail


class InboundEmailRouteType(Instance):
    """
    Claims inbound addresses that are not automation trigger tokens, e.g. an
    agent's own mailbox. The receiver's webhook offers every recipient on the
    inbound domain to the registered routes once no trigger matched.
    """

    def route(self, localpart: str, tag: str, email: "InboundEmail") -> Optional[str]:
        """
        :param localpart: The lowercased localpart without its `+tag`.
        :param tag: The `+tag` sub-address, empty when there is none.
        :param email: The normalized message.
        :return: A `HANDLE_STATUS_*` value when this route owns the address,
            None otherwise.
        """

        raise NotImplementedError


class InboundEmailRouteTypeRegistry(Registry[InboundEmailRouteType]):
    name = "inbound_email_route_type"


inbound_email_route_type_registry = InboundEmailRouteTypeRegistry()
