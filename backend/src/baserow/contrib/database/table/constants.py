TABLE_CREATION = "import-create-table"
USER_TABLE_DATABASE_NAME_PREFIX = "database_table_"
MULTIPLE_COLLABORATOR_THROUGH_TABLE_PREFIX = "database_multiplecollaborators_"
LINK_ROW_THROUGH_TABLE_PREFIX = "database_relation_"
MULTIPLE_SELECT_THROUGH_TABLE_PREFIX = "database_multipleselect_"


def get_tsv_vector_field_name(field_id) -> str:
    return f"tsv_field_{field_id}"


# This field was introduced initially for full text search. It is added to old user
# tables which existed prior dynamically at runtime when the table is loaded. It
# is intended to track which user rows have been changed and hence need various
# background tasks run in celery to say update indexes, send notifications etc.
# Currently the only "background job" that uses this column is the full text
# search tsv update.
ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME = "needs_background_update"
TSV_FIELD_PREFIX = "tsv_field"

LAST_MODIFIED_BY_COLUMN_NAME = "last_modified_by"
CREATED_BY_COLUMN_NAME = "created_by"
