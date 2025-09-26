import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from baserow.contrib.database.field_rules.registries import RowRuleChanges
    from baserow.contrib.database.table.models import GeneratedTableModel


@dataclass
class CascadeUpdatedRows:
    updated_rows: "list[GeneratedTableModel]"
    field_ids: set[int]
    row_ids: list[int]


class FieldRuleCollector:
    """
    Collects changes to rows made during field rules evaluation on row changes. If
    passed to a rule type handler, it can provide information if rows were changed
    by another rule.

    One instance of FieldRuleCollector should be created for one set of row changes.
    """

    starting_rows: list
    starting_rows_changed: list
    starting_rows_updated_field_ids: set
    starting_rows_processed_ids: set
    starting_rows_ids: set

    # output container
    processed_rows: list
    processed_rows_ids: set
    rows_cache: set
    processed_rows_updated_fields_ids: set

    def __init__(self, for_model: "GeneratedTableModel"):
        self.for_model = for_model
        self.reset()

    def set_starting_rows(self, rows: "list[GeneratedTableModel]"):
        self.starting_rows = rows
        self.starting_rows_ids = set([row.id for row in rows])

    def add_starting_rows(self, rows: "list[GeneratedTableModel]"):
        self.starting_rows.extend(rows)
        self.starting_rows_ids.update([r.id for r in rows])

    def is_starting_row_processed(self, row: "GeneratedTableModel"):
        return row.id in self.starting_rows_processed_ids

    def add_changes(self, changes: "list[RowRuleChanges]"):
        for change in changes:
            if change.row_id in self.starting_rows_ids or change.row_id is None:
                if change.row_id not in self.starting_rows_processed_ids:
                    self.starting_rows_changed.append(change)

                self.starting_rows_processed_ids.add(change.row_id)
                self.starting_rows_updated_field_ids.update(change.updated_field_ids)
            else:
                if change.row_id not in self.processed_rows_ids:
                    self.processed_rows.append(change)
                self.processed_rows_ids.add(change.row_id)
                self.processed_rows_updated_fields_ids.update(change.updated_field_ids)

    def get_processed_rows(self) -> CascadeUpdatedRows:
        """
        Returns information about rows that were processed during cascade update.
        """

        rows = [
            self.for_model(id=r.row_id, **r.updated_values) for r in self.processed_rows
        ]
        field_ids = self.processed_rows_updated_fields_ids
        row_ids = list(self.processed_rows_ids)
        return CascadeUpdatedRows(rows, field_ids, row_ids)

    @property
    def visited(self):
        return self.starting_rows_ids.union(self.processed_rows_ids)

    def reset(self):
        self.starting_rows = []
        self.starting_rows_changed = []
        self.starting_rows_updated_field_ids = set()
        self.starting_rows_processed_ids = set()
        self.starting_rows_ids = set()
        # output container
        self.processed_rows = []
        self.processed_rows_ids = set()
        self.rows_cache = set()
        self.processed_rows_updated_fields_ids = set()
