from typing import Dict, List, Set, cast

from django.db.models import Q

from baserow.contrib.database.fields.models import LinkRowField


def include_rows_connected_to_deleted_m2m_relationships(
    deleted_m2m_rels_per_link_field: Dict[int, Set[int]],
    path_to_starting_table: List[LinkRowField],
):
    """
    If a row or batch of rows have been updated breaking their link row connections
    with other rows, we need to ensure that those other rows are still updated.
    We can't just join back to the starting row id as that m2m relation has been
    deleted by now. Instead the provided dict contains per link field which rows
    have had their connections deleted. This method then constructs a Q filter that
    ensures this UPDATE statement will also update those rows as they need to
    change their values because a connection has been removed for them.

    :return: A filter including any rows which previously were connected to the
        starting row.
    """

    if deleted_m2m_rels_per_link_field is None or not path_to_starting_table:
        return Q()

    # The first link row field in the path will be a link row field not in the
    # starting table, but which leads to the starting table. However the
    # deleted_m2m_rels_per_link_field is a dictionary per link field of rows in
    # the table it links to which have had their connections removed. Hence we
    # need to use the link row field in the starting table to lookup the deleted
    # row ids in the table after the starting table.
    link_row_field_in_starting_table: int = cast(
        int, path_to_starting_table[-1].link_row_related_field_id
    )
    filters = Q()
    if link_row_field_in_starting_table in deleted_m2m_rels_per_link_field:
        path_to_table_after_starting_table = "".join(
            [p.db_column + "__" for p in path_to_starting_table[:-1]]
        )

        row_ids = deleted_m2m_rels_per_link_field[link_row_field_in_starting_table]
        filter_kwargs_forcing_update_for_row_with_deleted_rels = {
            f"{path_to_table_after_starting_table}id__in": row_ids
        }
        filters |= Q(**filter_kwargs_forcing_update_for_row_with_deleted_rels)
    return filters
