from abc import ABC

from baserow.contrib.builder.pages.operations import BuilderPageOperationType
from baserow.core.registries import OperationType


class ListDataSourcesPageOperationType(BuilderPageOperationType):
    type = "builder.page.list_data_sources"
    object_scope_name = "builder_data_source"


class OrderDataSourcesPageOperationType(BuilderPageOperationType):
    type = "builder.page.order_data_sources"
    object_scope_name = "builder_data_source"


class CreateDataSourceOperationType(BuilderPageOperationType):
    type = "builder.page.create_data_source"


class BuilderDataSourceOperationType(OperationType, ABC):
    context_scope_name = "builder_data_source"


class DeleteDataSourceOperationType(BuilderDataSourceOperationType):
    type = "builder.page.data_source.delete"


class UpdateDataSourceOperationType(BuilderDataSourceOperationType):
    type = "builder.page.data_source.update"


class ReadDataSourceOperationType(BuilderDataSourceOperationType):
    type = "builder.page.data_source.read"


class RestoreDataSourceOperationType(BuilderDataSourceOperationType):
    type = "builder.page.data_source.restore"


class DispatchDataSourceOperationType(BuilderDataSourceOperationType):
    type = "builder.page.data_source.dispatch"
