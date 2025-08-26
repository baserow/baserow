from baserow.config.celery import app


def call_strategy_method(self, method_name, **kwargs):
    from baserow.contrib.database.data_sync.handler import DataSyncHandler

    from .registries import data_sync_type_registry, two_way_sync_strategy_type_registry

    data_sync_id = kwargs.pop("data_sync_id")

    handler = DataSyncHandler()
    data_sync = handler.get_data_sync(data_sync_id=data_sync_id)
    kwargs["data_sync"] = data_sync
    kwargs["task_context"] = self

    data_sync_type = data_sync_type_registry.get_by_model(data_sync.specific_class)
    two_way_sync_type = two_way_sync_strategy_type_registry.get(
        data_sync_type.two_way_sync_strategy_type
    )
    getattr(two_way_sync_type, method_name)(**kwargs)


@app.task(bind=True, queue="export")
def two_way_sync_row_created(self, **kwargs):
    call_strategy_method(self, "rows_created", **kwargs)


@app.task(bind=True, queue="export")
def two_way_sync_row_updated(self, **kwargs):
    call_strategy_method(self, "rows_updated", **kwargs)


@app.task(bind=True, queue="export")
def two_way_sync_row_deleted(self, **kwargs):
    call_strategy_method(self, "rows_deleted", **kwargs)
