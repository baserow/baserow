import typing
from collections import defaultdict
from typing import Callable, Dict, List, Set, Tuple

if typing.TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.table.models import Table


class DeferredFieldImporter:
    """
    This class is used to import fields in the correct order based on their dependencies
    after all the fields without dependencies have been imported. This is useful when
    importing or duplicating a table with formulas or other fields that have
    dependencies.
    """

    def __init__(self):
        self.deferred_field_imports = {}
        self.field_import_callback_mapping = {}

    def _unique_field_name(self, table_id: int, field_name: str) -> str:
        return f"{table_id}:{field_name}"

    def add_deferred_field_import(
        self,
        table: "Table",
        field_name: str,
        field_dependencies: Set[Tuple[str, str]],
        import_field_callback: Callable,
    ) -> None:
        """
        Adds a field and its dependencies to the list of deferred field to import. The
        field will be imported in the right order once `run_deferred_field_imports` is
        called.

        :param table: The table the field belongs to.
        :param field_name: The name of the field.
        :param field_dependencies: A set of tuples where the first element is the name
            of the field that the field depends on and the second element is the name of
            the link row field to reach the target field. If the second element is None
            the target field is in the same table.
        :param import_field_callback: The callback that will import the field.
        """

        unique_field_name = self._unique_field_name(table.id, field_name)
        self.deferred_field_imports[unique_field_name] = (table, field_dependencies)
        self.field_import_callback_mapping[unique_field_name] = import_field_callback

    def get_all_fields_dependencies(
        self, field_name_fields_mapping: Dict[int, Dict[str, "Field"]]
    ) -> Dict[str, Set[str]]:
        """
        Merges all the field dependencies into a single dictionary. Dependencies use the
        table id and the field name to identify the field. The returned dictionary will
        have the field name as the key and a set of field names that it depends on as
        the value.

        :param field_name_fields_mapping: A mapping from table id to field name to field
        :return: A dictionary with the field name as the key and a set of field names
            representing the dependencies.
        """

        dependencies = defaultdict(set)

        for field_temp_id, (table, field_deps) in self.deferred_field_imports.items():
            for dep_field_name, via_field_name in field_deps:
                if via_field_name is not None:
                    try:
                        # The target field is in the linked table
                        link_row_field = field_name_fields_mapping[table.id][
                            via_field_name
                        ]
                        dep_table_id = link_row_field.link_row_table_id
                    except KeyError:
                        # If the `via_field_name` does not exist, then there is a
                        # broken dependency. In that case, it's okay to use the
                        # `table.id` as `dep_table_id` because it does not matter how
                        # it's grouped later.
                        dep_table_id = table.id
                else:
                    # The target field is in the same table
                    dep_table_id = table.id

                dep_field_temp_id = self._unique_field_name(
                    dep_table_id, dep_field_name
                )
                dependencies[field_temp_id].add(dep_field_temp_id)

        return dependencies

    def run_deferred_field_imports(
        self, field_name_fields_mapping: Dict[int, Dict[str, "Field"]]
    ) -> List["Field"]:
        """
        Performs the deferred field imports in the correct order. The fields will be
        imported in the correct order based on the dependencies. The dependencies are
        based on the table and field name. Because this happens at import time, we don't
        have the field instances yet, so we need to re-create the dependendency tree
        based on the field names and the table where they belong.

        :param field_name_fields_mapping: A mapping from table id to field name to field
        :return: The imported fields.
        """

        from baserow.contrib.database.fields.dependencies.handler import (
            FieldDependencyHandler,
        )

        dependencies = self.get_all_fields_dependencies(field_name_fields_mapping)

        # Now we can import the fields in the correct order
        imported_fields: List[Field] = []
        dependency_levels = FieldDependencyHandler.group_dependencies_by_level(
            dependencies
        )

        # The first level are the fields without dependencies, but we don't need to
        # import them because they have already been imported.
        for level in dependency_levels[1:]:
            for unique_field_name in level:
                import_field_callback = self.field_import_callback_mapping[
                    unique_field_name
                ]
                imported_field = import_field_callback()
                imported_fields.append(imported_field)

        return imported_fields
