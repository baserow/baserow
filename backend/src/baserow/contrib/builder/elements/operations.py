from abc import ABC

from baserow.contrib.builder.pages.operations import BuilderPageOperationType
from baserow.core.registries import OperationType


class ListElementsPageOperationType(BuilderPageOperationType):
    type = "builder.page.list_elements"
    object_scope_name = "builder_element"


class OrderElementsPageOperationType(BuilderPageOperationType):
    type = "builder.page.order_elements"
    object_scope_name = "builder_element"


class CreateElementOperationType(BuilderPageOperationType):
    type = "builder.page.create_element"


class BuilderElementOperationType(OperationType, ABC):
    context_scope_name = "builder_element"


class DeleteElementOperationType(BuilderElementOperationType):
    type = "builder.page.element.delete"


class UpdateElementOperationType(BuilderElementOperationType):
    type = "builder.page.element.update"


class ReadElementOperationType(BuilderElementOperationType):
    type = "builder.page.element.read"


class RestoreElementOperationType(BuilderElementOperationType):
    type = "builder.page.element.restore"
