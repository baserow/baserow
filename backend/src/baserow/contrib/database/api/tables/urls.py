from django.urls import re_path

from .views import (
    AllTablesView,
    AsyncCreateTableView,
    AsyncDuplicateTableView,
    AsyncTableImportView,
    OrderTablesView,
    TablesView,
    TableView,
)

app_name = "baserow.contrib.database.api.tables"

urlpatterns = [
    re_path(r"all-tables/$", AllTablesView.as_view(), name="all_tables"),
    re_path(r"database/(?P<database_id>[0-9]+)/$", TablesView.as_view(), name="list"),
    re_path(
        r"database/(?P<database_id>[0-9]+)/async/$",
        AsyncCreateTableView.as_view(),
        name="async_create",
    ),
    re_path(
        r"database/(?P<database_id>[0-9]+)/order/$",
        OrderTablesView.as_view(),
        name="order",
    ),
    re_path(
        r"(?P<table_id>[0-9]+)/duplicate/async/$",
        AsyncDuplicateTableView.as_view(),
        name="async_duplicate",
    ),
    re_path(r"(?P<table_id>[0-9]+)/$", TableView.as_view(), name="item"),
    re_path(
        r"(?P<table_id>[0-9]+)/import/async/$",
        AsyncTableImportView.as_view(),
        name="import_async",
    ),
]
