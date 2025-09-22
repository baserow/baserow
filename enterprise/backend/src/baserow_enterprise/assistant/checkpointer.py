import os
from typing import Optional

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from baserow.core.db import get_database_dsn

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None


def get_pool() -> AsyncConnectionPool:
    """
    Get the database connection pool.
    """

    global _pool

    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=get_database_dsn(),
            min_size=1,
            max_size=os.getenv("LANGGRAPH_PG_POOL_MAX", 10),
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,  # Prevent RuntimeWarning for implicit opening
        )
    return _pool


async def get_checkpointer() -> AsyncPostgresSaver:
    """
    Get the checkpointer for the database. A checkpointer is responsible for saving and
    loading the state of a graph to/from a persistent storage. In this case, we use
    Postgres as the storage backend to persist the state of the graph. The state
    contains the inputs, outputs and intermediate values of the nodes in the graph,
    allowing us to resume execution from the last saved state in case of failures.

    This function initializes the checkpointer if it hasn't been created yet, setting up
    the connection pool and serializer. It ensures that the checkpointer is ready to use
    for saving and loading graph states, by creating the necessary database tables if
    they do not already exist, or migrating them if the schema has changed, via the
    `setup` method.
    """

    global _checkpointer
    if _checkpointer is None:
        pool = get_pool()
        await pool.open()
        _checkpointer = AsyncPostgresSaver(pool, serde=JsonPlusSerializer())
        await _checkpointer.setup()
    return _checkpointer
