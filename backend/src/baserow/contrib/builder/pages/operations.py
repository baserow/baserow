from abc import ABC

from baserow.contrib.builder.operations import BuilderOperationType


class BuilderPageOperationType(BuilderOperationType, ABC):
    context_scope_name = "builder_page"


class CreatePageOperationType(BuilderOperationType):
    type = "builder.create_page"


class DeletePageOperationType(BuilderPageOperationType):
    type = "builder.page.delete"


class UpdatePageOperationType(BuilderPageOperationType):
    type = "builder.page.update"


class ReadPageOperationType(BuilderPageOperationType):
    type = "builder.page.read"


class DuplicatePageOperationType(BuilderPageOperationType):
    type = "builder.page.duplicate"


class RestorePageOperationType(BuilderPageOperationType):
    type = "builder.page.restore"
