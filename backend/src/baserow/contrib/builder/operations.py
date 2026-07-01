from abc import ABCMeta

from baserow.core.registries import OperationType


class BuilderOperationType(OperationType, metaclass=ABCMeta):
    context_scope_name = "builder"


class ListPagesBuilderOperationType(BuilderOperationType):
    type = "builder.list_pages"
    object_scope_name = "builder_page"


class OrderPagesBuilderOperationType(BuilderOperationType):
    type = "builder.order_pages"


class ListDomainsBuilderOperationType(BuilderOperationType):
    type = "builder.list_domains"
    object_scope_name = "builder_domain"


class OrderDomainsBuilderOperationType(BuilderOperationType):
    type = "builder.order_domains"
