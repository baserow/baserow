from dataclasses import dataclass
from typing import Any, Dict, NewType

from .models import DataSource

DataSourceForUpdate = NewType("DataSourceForUpdate", DataSource)


@dataclass
class UpdatedDataSource:
    data_source: DataSource
    original_values: Dict[str, Any]
    new_values: Dict[str, Any]
