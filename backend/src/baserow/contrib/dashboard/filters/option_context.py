import json

from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpRequest

from baserow.contrib.dashboard.data_providers import (
    dashboard_filter_options_data_provider_type_registry,
)
from baserow.contrib.dashboard.filters.exceptions import DashboardFilterOptionsTooLarge
from baserow.contrib.dashboard.models import Dashboard
from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext


class DashboardFilterOptionsContext(RuntimeFormulaContext):
    """Evaluate option formulas with table access and mandatory input limits."""

    data_provider_registry = dashboard_filter_options_data_provider_type_registry

    def __init__(
        self,
        request: HttpRequest,
        dashboard: Dashboard,
        *,
        max_records: int,
        max_bytes: int,
    ):
        super().__init__()
        self.request = request
        self.dashboard = dashboard
        self.max_records = max_records
        self.max_bytes = max_bytes
        self.cache = {}
        self.table_ids_read: set[int] = set()
        self.records_read = 0
        self.bytes_read = 0

    def consume_record(self, record):
        """Count all projected records, including separate reads of one table."""

        self.records_read += 1
        self.bytes_read += len(json.dumps(record, cls=DjangoJSONEncoder).encode())
        if self.records_read > self.max_records or self.bytes_read > self.max_bytes:
            raise DashboardFilterOptionsTooLarge()
